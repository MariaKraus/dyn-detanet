
import os
from torch_geometric.loader import DataLoader
from torch_geometric.loader import DataLoader

import trainer
from detanet_model import *
import utils as ut

import wandb
import random
seed = 3512
random.seed(seed)

batch_size = 16
epochs = 100
lr= 0.0005
cutoff=6


num_block=6
num_features=128
attention_head=32
num_radial=32

scalar_outsize= (4* 61)
irreps_out= '122x2e'
out_type = 'multi_tensor'
target = 'y'
dataset_name = 'QM9SPol'
x_features = 0
dropout = 0.2

finetune = False
finetune_file = '/home/maria/dyn-detanet/code/trained_param/dynamic-polarizability/OPT_QM9SPol_NoSpectra0features70epochs_64batchsize_0.0005lr_6cutoff_6numblock_128features_KITQM9.pth'

name = f"App1_{x_features}spectra{epochs}epochs_{batch_size}batchsize_{lr}lr_{cutoff}cutoff_{num_block}numblock_{num_features}features_{attention_head}att_{dataset_name}_seed{seed}"

# -------------------------------

current_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = os.path.dirname(current_dir)
data_dir = os.path.join(parent_dir, 'data')

dataset = []

# Load the dataset
dataset = torch.load(os.path.join(data_dir, dataset_name + '.pt'))
print(f"Number of graphs in the dataset: {len(dataset)}")

ex1 = dataset[0]
ex2 = dataset[5]
print("dataset[0] :", ex1, )
print("dataset[5] :", ex2,)

# Subtract static polarizability
for data in dataset:
    data.real_ee = data.real_ee[1:] - data.real_ee[0]
    data.imag_ee = data.imag_ee[1:] # Imaginary part at freq 0 is 0 anyways

    data.y = torch.cat([data.real_ee, data.imag_ee], dim=0)

    if x_features == 61:
        data.x = data.spectra[1:].repeat(len(data.z), 1)


# -------------------------------
# Shuffle & Train/Val Split
# -------------------------------
random.shuffle(dataset)
train_frac = 0.9
split_index = int(train_frac * len(dataset))

train_datasets = dataset[:split_index]
val_datasets   = dataset[split_index:]

val_dataset_to_print = []
for mol in val_datasets:
    val_dataset_to_print.append(str(mol.idx))
print("Validation dataset indices:", val_dataset_to_print)

print(f"Training set size: {len(train_datasets)}")
print(f"Validation set size: {len(val_datasets)}")



# Dataloaders
trainloader = DataLoader(train_datasets, batch_size=batch_size, shuffle=True,  drop_last=False)
valloader   = DataLoader(val_datasets,   batch_size=batch_size, shuffle=False, drop_last=False)


wandb.init(
    # set the wandb project where this run will be logged
    project="OPT-configs",
    name=name,
    # track hyperparameters and run metadata
    config={
    "learning_rate": lr,
    "architecture": "GNN",
    "dataset": dataset_name,
    "epochs": epochs,
    }
)

device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")

model = DetaNet(num_features=num_features,
                    act='swish',
                    maxl=3,
                    num_block=num_block, 
                    radial_type='trainable_bessel',
                    num_radial=num_radial,
                    attention_head=attention_head,
                    rc=cutoff,
                    dropout=dropout,
                    use_cutoff=False,
                    max_atomic_number=34,
                    atom_ref=None,
                    scale=1.0,
                    scalar_outsize=scalar_outsize, 
                    irreps_out= irreps_out,
                    summation=True,
                    norm=False,
                    out_type=out_type,
                    grad_type=None,
                    x_features=x_features,
                    device=device)
if finetune:
    state_dict=torch.load(finetune_file)
    model.load_state_dict(state_dict=state_dict)
    print("Model loaded from checkpoint")
model.train()
model.to(device)
wandb.watch(model, log="all")


trainer_ = trainer.Trainer(
    model,
    train_loader=trainloader,
    val_loader=valloader,
    loss_function=l2loss, 
    lr=lr,
    weight_decay=0,
    optimizer='AdamW'
)

trainer_.train(num_train=epochs, targ=target)

torch.save(model.state_dict(), os.path.join(current_dir, 'trained_param', name + '.pth'))
