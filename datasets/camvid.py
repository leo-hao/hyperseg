from __future__ import print_function

import os
import torch
# import torch.utils.data as data
from torchvision.datasets.folder import is_image_file, default_loader
from torchvision.datasets.vision import VisionDataset
import numpy as np
from PIL import Image


classes = ['Sky', 'Building', 'Column-Pole', 'Road', 'Sidewalk', 'Tree', 'Sign-Symbol', 'Fence', 'Car', 'Pedestrain',
           'Bicyclist', 'Void']


# weights when using median frequency balancing used in SegNet paper
# https://arxiv.org/pdf/1511.00561.pdf
# The numbers were generated by https://github.com/yandex/segnet-torch/blob/master/datasets/camvid-gen.lua
class_weight = [0.58872014284134, 0.51052379608154, 2.6966278553009, 0.45021694898605, 1.1785038709641,
                0.77028578519821, 2.4782588481903, 2.5273461341858, 1.0122526884079, 3.2375309467316,
                4.1312313079834, 0]
# mean and std
mean = [0.41189489566336, 0.4251328133025, 0.4326707089857]
std = [0.27413549931506, 0.28506257482912, 0.28284674400252]

class_color = [
    (128, 128, 128),
    (128, 0, 0),
    (192, 192, 128),
    (128, 64, 128),
    (0, 0, 192),
    (128, 128, 0),
    (192, 128, 128),
    (64, 64, 128),
    (64, 0, 128),
    (64, 64, 0),
    (0, 128, 192),
    (0, 0, 0),
]


def _make_dataset(dir):
    images = []
    for root, _, fnames in sorted(os.walk(dir)):
        for fname in fnames:
            if is_image_file(fname):
                path = os.path.join(root, fname)
                item = path
                images.append(item)
    return images


# Download from: https://www.kaggle.com/carlolepelaars/camvid#
class CamVidDataset(VisionDataset):
    """ Cambridge-driving Labeled Video Database (CamVid) `<http://mi.eng.cam.ac.uk/research/projects/VideoRec/CamVid>`_
        dataset.

    Args:
        root (str): Root directory of the dataset.
        split (str, list[str]): Select the splits to use, ``train``, ``val`` or ``test``.
        transform (callable, optional): A function/transform that  takes in an PIL image
            and returns a transformed version. E.g, ``transforms.RandomCrop``
        target_transform (callable, optional): A function/transform that takes in the
            target and transforms it.
        transforms (callable, optional): A function/transform that takes input sample and its target as entry
            and returns a transformed version.
    """
    def __init__(self, root, split='train', transform=None, target_transform=None, transforms=None):
        super(CamVidDataset, self).__init__(root, transforms, transform, target_transform)
        split = [split] if isinstance(split, str) else split
        for s in split:
            assert s in ('train', 'val', 'test')
        self.split = split
        self.class_weight = class_weight
        self.classes = classes
        self.weights = class_weight
        self.color_map = class_color
        self.mean = mean
        self.std = std
        self.target2tensor = LabelToLongTensor()

        self.images, self.masks = [], []
        for s in split:
            curr_images = _make_dataset(os.path.join(self.root, s))
            self.images += curr_images
            self.masks += [p.replace(s, s + '_labels').replace('.', '_L.') for p in curr_images]

        # Validate files
        for img_path, mask_path in zip(self.images, self.masks):
            assert os.path.isfile(img_path), f'Image file is missing: "{img_path}"'
            assert os.path.isfile(mask_path), f'Label file is missing: "{mask_path}"'
        assert len(self.images) > 0, f'Failed to find any images in "{root}"'

    def convert_label(self, label):
        label_rgb = np.array(label)
        # label_index = np.zeros(label_rgb.shape[:2], dtype='uint8')
        label_index = np.full(label_rgb.shape[:2], 255, dtype='uint8')
        for i, color in enumerate(self.color_map):
            label_index[np.all(label_rgb == color, axis=2)] = i

        label_index = Image.fromarray(label_index, mode='P')

        return label_index

    def __getitem__(self, index):
        img = Image.open(self.images[index]).convert('RGB')
        target = self.convert_label(Image.open(self.masks[index]))
        if np.array(target).ndim == 3:
            print(np.array(target).shape)
        if self.transforms is not None:
            img, target = self.transforms(img, target)

        # return img, target.long().unsqueeze(0)
        return img, np.array(target).astype('int64')

    def __len__(self):
        return len(self.images)


class LabelToLongTensor(object):
    def __call__(self, pic):
        if isinstance(pic, np.ndarray):
            # handle numpy array
            label = torch.from_numpy(pic).long()
        else:
            label = torch.ByteTensor(torch.ByteStorage.from_buffer(pic.tobytes()))
            label = label.view(pic.size[1], pic.size[0], 1)
            label = label.transpose(0, 1).transpose(0, 2).squeeze().contiguous().long()
        return label


class LabelTensorToPILImage(object):
    def __call__(self, label):
        label = label.unsqueeze(0)
        colored_label = torch.zeros(3, label.size(1), label.size(2)).byte()
        for i, color in enumerate(class_color):
            mask = label.eq(i)
            for j in range(3):
                colored_label[j].masked_fill_(mask, color[j])
        npimg = colored_label.numpy()
        npimg = np.transpose(npimg, (1, 2, 0))
        mode = None
        if npimg.shape[2] == 1:
            npimg = npimg[:, :, 0]
            mode = "L"

        return Image.fromarray(npimg, mode=mode)


def main(dataset='hyperseg.datasets.camvid.CamVidDataset',
         train_img_transforms=None, val_img_transforms=None,
         tensor_transforms=('seg_transforms.ToTensor', 'seg_transforms.Normalize'),
         workers=4, batch_size=4):
    from hyperseg.utils.obj_factory import obj_factory

    dataset = obj_factory(dataset)
    for img, target in dataset:
        print(img)
        print(target.shape)
    print(len(dataset))


if __name__ == "__main__":
    # Parse program arguments
    import argparse
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('dataset', metavar='OBJ', default='hyperseg.datasets.camvid.CamVidDataset',
                        help='dataset object')
    parser.add_argument('-tit', '--train_img_transforms', nargs='+',
                        help='train image transforms')
    parser.add_argument('-vit', '--val_img_transforms', nargs='+',
                        help='validation image transforms')
    parser.add_argument('-tt', '--tensor_transforms', nargs='+', help='tensor transforms',
                        default=('seg_transforms.ToTensor', 'seg_transforms.Normalize'))
    parser.add_argument('-w', '--workers', default=4, type=int, metavar='N',
                        help='number of data loading workers')
    parser.add_argument('-b', '--batch-size', default=4, type=int, metavar='N',
                        help='mini-batch size')
    main(**vars(parser.parse_args()))
