import argparse

import torch
import torchvision
from torch.utils.tensorboard import SummaryWriter  # needed for using TensorBoard

EPOCHS = 100  # max number
BATCH_SIZE = 32  # how many images will be used in each epoch

xy_trainPT = torchvision.datasets.MNIST(
    root="./data",
    train=True,
    download=True,
    transform=torchvision.transforms.Compose([torchvision.transforms.ToTensor()]),
)
xy_trainPT_loader = torch.utils.data.DataLoader(xy_trainPT, batch_size=BATCH_SIZE)


# create a tiny toy model with four layers
def model(hidden):
    model = torch.nn.Sequential(
        torch.nn.Linear(784, hidden),
        torch.nn.Sigmoid(),
        torch.nn.Linear(hidden, 10),
        torch.nn.LogSoftmax(dim=1),
    )
    return model


model_instance = model(10)
criterion = torch.nn.NLLLoss()  # use the negative log likelihood loss.
optimizer = torch.optim.SGD(
    model_instance.parameters(), lr=0.01
)  # use SGD (Stochastic Gradient Descent gradient descent) optimization algorithm

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--log_dir", type=str, help="tensorboard log path")
    args = parser.parse_args()
    writer = SummaryWriter(log_dir=args.log_dir)
    for e in range(EPOCHS):
        running_loss = 0
        for images, labels in xy_trainPT_loader:
            images = images.view(images.shape[0], -1)
            output = model(images)
            loss = criterion(output, labels)
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()
            running_loss += loss.item()
        print(
            "Epoch {} - Training loss: {}".format(
                e, running_loss/len(xy_trainPT_loader)
            )
        )
        writer.add_scalar("loss vs epoch", running_loss / len(xy_trainPT_loader), e)
    writer.flush()
    writer.close()
