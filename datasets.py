import json
import cv2
import os
import numpy as np
from torch.utils.data import Dataset


def get_dataset(root_path, data_path):
    dataset = InpaintingDataset(root_path, data_path)
    return dataset


class InpaintingDataset(Dataset):
    def __init__(self, root_path, data_path):
        self.data = []
        with open(data_path, "rt") as f:
            for line in f:
                json_dict = json.loads(line)
                for k, v in json_dict.items():
                    json_dict[k] = os.path.join(root_path, v)
                self.data.append(json_dict)
        f.close()

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]

        dense_filename = item["dense"]
        sparse_filename = item["sparse"]
        pose_filename = item["pose"]
        text_filename = item["text"]
        
        dense = cv2.imread(dense_filename)
        sparse = cv2.imread(sparse_filename)
        pose = cv2.imread(pose_filename)
        f = open(text_filename, "r")
        text = f.readline()
        f.close()

        dense = cv2.resize(dense, (512, 512))
        sparse = cv2.resize(sparse, (512, 512))
        pose = cv2.resize(pose, (512, 512))

        dense = cv2.cvtColor(dense, cv2.COLOR_BGR2RGB)
        sparse = cv2.cvtColor(sparse, cv2.COLOR_BGR2RGB)
        pose = cv2.cvtColor(pose, cv2.COLOR_BGR2RGB)
        
        dense = (dense.astype(np.float32) / 127.5) - 1.0
        sparse = (sparse.astype(np.float32) / 127.5) - 1.0
        pose = pose.astype(np.float32) / 255.0

        batch = {
            "jpg": dense,
            "txt": text,
            "mask": pose,
            "masked_image": sparse,
        }
        return batch
