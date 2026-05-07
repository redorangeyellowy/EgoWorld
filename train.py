import os
import argparse
from torch.utils.data import DataLoader
import pytorch_lightning as pl
from pytorch_lightning.callbacks import ModelCheckpoint

from datasets import get_dataset
from cldm.model import create_model, load_state_dict
from cldm.hack import disable_verbosity
from cldm.logger import ImageLogger
disable_verbosity()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_name", type=str, dest="dataset_name", default="h2o_action")
    parser.add_argument("--project_name", type=str, dest="project_name", default= "inpainting")
    parser.add_argument("--json_name", type=str, dest="json_name", default="train")
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
    model.learning_rate = 1e-5
    model.sd_locked = False
    model.only_mid_control = False

    # Misc
    data_path = os.path.join("data", dataset_name, project_name, f"{json_name}.json")
    dataset = get_dataset(root_path, data_path)
    dataloader = DataLoader(dataset, num_workers=0, batch_size=3, shuffle=True)
    log_folder = os.path.join("logs", dataset_name, project_name)
    os.makedirs(log_folder, exist_ok=True)

    # Train!
    logger = ImageLogger(batch_frequency=200, ckpt_name=pretrained_path.split("/")[-1][:-5])
    checkpoint_callback = ModelCheckpoint(
        filename=f"{{step}}",
        save_top_k=-1,
        save_weights_only=False,
        every_n_train_steps=1000
    )
    trainer = pl.Trainer(
        default_root_dir=log_folder,
        gpus=1, 
        precision=32, 
        callbacks=[logger, checkpoint_callback], 
        max_epochs=5
    )
    trainer.fit(model, dataloader)

    print("Train Finished.")