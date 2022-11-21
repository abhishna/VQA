from dataset import VQADataset
from models.baseline import VQABaseline
from PIL import Image
from torch.optim import SGD, lr_scheduler
from torch.utils.data import Dataset, DataLoader
from train import *
from utils import *

import argparse
import os
import numpy as np
import pickle
import torch
import torch.nn as nn
import torchvision.transforms as transforms

random_seed  = 43
torch.manual_seed(random_seed)

parser = argparse.ArgumentParser(description='VQA')

def get_model(vocab_size):
    return VQABaseline(vocab_size = vocab_size)

device     = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
data_dir   = "/scratch/crg9968/datasets"
model_dir  = "/scratch/crg9968/checkpoints"
log_dir    = "/scratch/crg9968/logs"

vocab_size = len(pickle.load(open(os.path.join(data_dir, 'questions_vocab.pkl'), 'rb'))["word2idx"])

transform  = transforms.Compose([
                 transforms.CenterCrop(224),
                 transforms.ToTensor(),
                 transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])])
top_k     = 1000
train_ds  = VQADataset(data_dir, top_k = top_k, transform = transform)
val_ds    = VQADataset(data_dir, mode = 'val', top_k = top_k, transform = transform)
test_ds   = VQADataset(data_dir, mode = 'test', top_k = top_k, transform = transform)

num_gpus     = torch.cuda.device_count()
batch_size   = 64
if num_gpus: # Same batch size on each GPU
    batch_size *= num_gpus
train_loader = DataLoader(train_ds, batch_size = batch_size, shuffle = True, num_workers = 2, pin_memory = True)
val_loader   = DataLoader(val_ds, batch_size = batch_size, num_workers = 2, pin_memory = True)
test_loader  = DataLoader(test_ds, batch_size = batch_size, num_workers = 2, pin_memory = True)

# DECIDE THE PARAMETERS FROM THE PAPER
lr           = 0.01
momentum     = 0.9
weight_decay = 0.0005
epochs       = 2

model        = nn.DataParallel(get_model(vocab_size)).to(device) if num_gpus > 1 else get_model(vocab_size).to(device)
optimizer    = SGD(model.parameters(), lr = lr, momentum = momentum, weight_decay = weight_decay)
loss_fn      = nn.CrossEntropyLoss()
scheduler    = lr_scheduler.MultiStepLR(optimizer, milestones = [60, 120, 180], gamma = 0.1)
# DECIDE THE SCHEDULER FROM THE PAPERS

model_name   = 'testrun'
model, optim, best_accuracy, train_losses, train_accuracies, val_losses, val_accuracies = \
    train_model(model, train_loader, val_loader, loss_fn, optimizer, scheduler, device,
                model_dir, log_dir, epochs = epochs, model_name = model_name)

model, test_accuracy = test_model(model, test_loader, device)

parse_tb_logs(log_dir, model_name, 'epoch')
parse_tb_logs(log_dir, model_name, 'step')
