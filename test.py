import os
import argparse
from torch.utils.data import DataLoader
from pytorch_lightning import seed_everything
import torch
import torchvision
import cv2
import numpy as np
import random
from tqdm import tqdm
from einops import rearrange

from datasets import get_dataset
from cldm.model import create_model, load_state_dict
from cldm.hack import disable_verbosity
from ldm.models.diffusion.ddim import DDIMSampler
from ldm.util import log_txt_as_img
disable_verbosity()


def process(model, ddim_sampler, prompt=None, mask=None, masked_image=None, a_prompt="", n_prompt="", num_samples=4, ddim_steps=20, guess_mode=False, strength=1.0, scale=1.0, seed=42, eta=1.0):
    if seed == -1:
        seed = random.randint(0, 65535)
    # seed_everything(seed)
    
    prng = np.random.RandomState(seed)
    start_code = prng.randn(num_samples, 4, 64, 64)
    start_code = torch.from_numpy(start_code).to(device=model.device, dtype=torch.float32)

    with torch.no_grad():
        c = model.get_learned_conditioning([prompt[0]] * num_samples)
        c_cat = list()
        bchw = (num_samples, 4, 64, 64)
        batch = {"mask": mask.repeat(num_samples, 1, 1, 1).to(model.device), "masked_image": masked_image.repeat(num_samples, 1, 1, 1).to(model.device)}
        for ck in batch.keys():
            cc = rearrange(batch[ck], "b h w c -> b c h w").to(memory_format=torch.contiguous_format).float()
            cc = model.get_first_stage_encoding(model.encode_first_stage(cc))
            if ck == "mask":
                cc = model.channel_reducer(cc)
            c_cat.append(cc)
        c_cat = torch.cat(c_cat, dim=1)
        cond = {"c_concat": [c_cat], "c_crossattn": [c]}
        if scale > 1.0:
            un_cond = {"c_concat": [c_cat], "c_crossattn": [model.get_learned_conditioning([n_prompt] * num_samples)]}
        else:
            un_cond = None
        mask = None
        x0 = None

        model.control_scales = [strength * (0.825 ** float(12 - i)) for i in range(13)] if guess_mode else ([strength] * 13)
        shape = (4, 64, 64)
        samples, intermediates = ddim_sampler.sample(
            ddim_steps, 
            num_samples, 
            shape, 
            cond, 
            verbose=False, 
            eta=eta,
            unconditional_guidance_scale=scale,
            unconditional_conditioning=un_cond,
            x_T=start_code,
            x0=x0,
            mask=mask
        )
    
        x_samples = model.decode_first_stage(samples)
        x_samples = (rearrange(x_samples, "b c h w -> b h w c") * 127.5 + 127.5).cpu().numpy().clip(0, 255).astype(np.uint8)
        results = [x_samples[i] for i in range(num_samples)]
    
    return results


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_name", type=str, dest="dataset_name", default="h2o_action")
    parser.add_argument("--project_name", type=str, dest="project_name", default= "inpainting")
    parser.add_argument("--json_name", type=str, dest="json_name", default="test")
    parser.add_argument("--pretrained_path", type=str, dest="pretrained_path", default="checkpoints/sd-v1-5-inpainting.ckpt")
    parser.add_argument("--root_path", type=str, dest="root_path", default="")
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_args()

    # Configs
    dataset_name = args.dataset_name
    project_name = args.project_name
    json_name = args.json_name
    pretrained_path = args.pretrained_path
    root_path = args.root_path

    # Model
    model = create_model(f"./models/{project_name}.yaml").cpu()
    model.load_state_dict(load_state_dict(pretrained_path, location="cpu"), strict=False)
    model = model.cuda()
    sampler = DDIMSampler(model)
    
    # Misc
    data_path = os.path.join("data", dataset_name, project_name, f"{json_name}.json")
    dataset = get_dataset(root_path, data_path)
    dataloader = DataLoader(dataset, num_workers=0, batch_size=1, shuffle=False)
    log_folder = pretrained_path.replace("checkpoints", "images").replace(".ckpt", f"/{json_name}")
    os.makedirs(log_folder, exist_ok=True)
    
    # Test!
    for i, batch in enumerate(tqdm(dataloader, desc="dataloader")):
        save_path_gt = os.path.join(log_folder, f"{str(i).zfill(6)}_gt.png")
        save_path_input = os.path.join(log_folder, f"{str(i).zfill(6)}_input.png")
        save_path_output_uc10 = os.path.join(log_folder, f"{str(i).zfill(6)}_output_uc10.png")
        save_path_output_uc90 = os.path.join(log_folder, f"{str(i).zfill(6)}_output_uc90.png")
        save_path_output_uc75 = os.path.join(log_folder, f"{str(i).zfill(6)}_output_uc75.png")
        output_uc10 = process(model, sampler, num_samples=4, prompt=batch["txt"], mask=batch["mask"], masked_image=batch["masked_image"])
        output_uc90 = process(model, sampler, num_samples=4, prompt=batch["txt"], mask=batch["mask"], masked_image=batch["masked_image"], scale=9.0)
        output_uc75 = process(model, sampler, num_samples=4, prompt=batch["txt"], mask=batch["mask"], masked_image=batch["masked_image"], scale=7.5)
        input = []
        for k, v in batch.items():
            if k == "txt" and not torch.is_tensor(v):
                v = log_txt_as_img((512, 512), v, size=20).squeeze(0)
                v = v.transpose(0, 1).transpose(1, 2)
            v = torchvision.utils.make_grid(v, padding=0)
            if k != "mask":
                v = (v + 1.0) / 2.0
            v = v.numpy()
            v = (v * 255).astype(np.uint8)
            v = cv2.cvtColor(v, cv2.COLOR_BGR2RGB)
            if k == "jpg":
                cv2.imwrite(save_path_gt, v)
            else:
                input.append(v)
        input = np.concatenate(input, axis=1)
        cv2.imwrite(save_path_input, input)
        for (output, save_path_output) in zip([output_uc10, output_uc90, output_uc75], [save_path_output_uc10, save_path_output_uc90, save_path_output_uc75]):
            if output is not None:
                output = [cv2.cvtColor(out, cv2.COLOR_BGR2RGB) for out in output]
                output = np.concatenate(output, axis=1)
                cv2.imwrite(save_path_output, output)

    print("Test Finished.")