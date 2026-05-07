import os
from glob import glob
import cv2
import shutil

import numpy as np
import torch
import torchvision
from PIL import Image
from pytorch_lightning.callbacks import Callback
from pytorch_lightning.utilities.distributed import rank_zero_only


class ImageLogger(Callback):
    def __init__(self, batch_frequency=2000, max_images=4, clamp=True, increase_log_steps=True,
                 rescale=True, disabled=False, log_on_batch_idx=False, log_first_step=False,
                 log_images_kwargs=None, ckpt_name=None):
        super().__init__()
        self.rescale = rescale
        self.batch_freq = batch_frequency
        self.max_images = max_images
        if not increase_log_steps:
            self.log_steps = [self.batch_freq]
        self.clamp = clamp
        self.disabled = disabled
        self.log_on_batch_idx = log_on_batch_idx
        self.log_images_kwargs = log_images_kwargs if log_images_kwargs else {}
        self.log_first_step = log_first_step
        self.ckpt_name = ckpt_name

    @rank_zero_only
    def log_local(self, save_dir, split, images, prompts, global_step, current_epoch, batch_idx):
        root = os.path.join(save_dir, "image_logs", self.ckpt_name, split)
        for k in images:
            filename = "gs-{:06}_e-{:06}_b-{:06}_{}.png".format(global_step, current_epoch, batch_idx, k)
            path = os.path.join(root, filename)
            os.makedirs(os.path.split(path)[0], exist_ok=True)
            grid = torchvision.utils.make_grid(images[k], nrow=4)
            if self.rescale:
                grid = (grid + 1.0) / 2.0  # -1,1 -> 0,1; c,h,w
            grid = grid.transpose(0, 1).transpose(1, 2).squeeze(-1)
            grid = grid.numpy()
            grid = (grid * 255).astype(np.uint8)
            Image.fromarray(grid).save(path)

        if not torch.is_tensor(prompts):
            if prompts:
                filename = "gs-{:06}_e-{:06}_b-{:06}_{}.txt".format(global_step, current_epoch, batch_idx, "prompt")
                path = os.path.join(root, filename)
                f = open(path, 'w')
                for prompt in prompts:
                    f.write(prompt)
                    f.write('\n')
                f.close()
                if '.png' in prompts[0]:
                    for pi, prompt in enumerate(prompts):
                        filename = "gs-{:06}_e-{:06}_b-{:06}_{}_{}.png".format(global_step, current_epoch, batch_idx, "prompt", pi)
                        path = os.path.join(root, filename)
                        shutil.copy(prompt, path)

    def log_img(self, pl_module, batch, batch_idx, split="train"):
        check_idx = batch_idx  # if self.log_on_batch_idx else pl_module.global_step
        if (self.check_frequency(check_idx) and  # batch_idx % self.batch_freq == 0
                hasattr(pl_module, "log_images") and
                callable(pl_module.log_images) and
                self.max_images > 0):
            logger = type(pl_module.logger)

            is_train = pl_module.training
            if is_train:
                pl_module.eval()

            with torch.no_grad():
                images = pl_module.log_images(batch, split=split, **self.log_images_kwargs)
                if "txt" in batch:
                    prompts = batch["txt"]
                else:
                    prompts = None
                
            for k in images:
                N = min(images[k].shape[0], self.max_images)
                images[k] = images[k][:N]
                if isinstance(images[k], torch.Tensor):
                    images[k] = images[k].detach().cpu()
                    if self.clamp:
                        images[k] = torch.clamp(images[k], -1., 1.)

            self.log_local(pl_module.logger.save_dir, split, images, prompts,
                           pl_module.global_step, pl_module.current_epoch, batch_idx)

            if is_train:
                pl_module.train()

    def check_frequency(self, check_idx):
        return check_idx % self.batch_freq == 0

    def on_train_batch_end(self, trainer, pl_module, outputs, batch, batch_idx, dataloader_idx):
        if not self.disabled:
            self.log_img(pl_module, batch, batch_idx, split="train")
