import torch
import pandas as pd
import pandas.api.typing as pd_typing
from typing import List
from PIL import Image
import torchvision
from typing import Tuple


def get_dataframe(path_to_csvs: str) -> pd.DataFrame:
    """
    Returns a DataFrame object grouped by the mover_id with columns file_name and label
    """
    # Read csv
    real_movers = pd.read_csv(path_to_csvs + "movers_images_lookup.csv")
    bogus_movers = pd.read_csv(path_to_csvs + "rejected_movers_images_lookup.csv")

    # Add labels
    real_movers["label"] = 1
    bogus_movers["label"] = 0

    # Group by mover
    movers = pd.concat([real_movers, bogus_movers])
    movers_agg = movers.groupby("mover_id")
    return movers_agg


def get_dataset(
    movers_agg: pd_typing.DataFrameGroupBy,
    path_to_images: str,
    image_shape: Tuple[int, int] = (30, 30),
) -> Tuple[torch.utils.data.TensorDataset, List[str]]:
    """
    Creates a dataset of (input, output) pairs.
    Filters out movers that don't have 4 images or match the expected shape.

    Args:
        movers_agg (DataFrameGroupBy): The image entries of the data frame grouped by the mover they belong to.
        path_to_images (str): Path to the image folder
        image_shape (Tuple[int, int]): Desired image width and height.

    Returns: Dataset and list of the mover ids that were actually used.
    """
    x_tensors = []
    y_hat_tensors = []
    mover_ids = []
    for mover_id, group_data in movers_agg:
        image_tensors = []
        # Ignore sequences that aren't 4 images long
        if len(group_data) != 4:
            print(f"Skipping {mover_id} sequence with length: {len(group_data)}")
            continue

        for _, row in group_data.iterrows():
            image_path = path_to_images + row["file_name"]
            try:
                # Read image as PIL Image and convert to grayscale
                image = Image.open(image_path).convert("L")
            except FileNotFoundError:
                print(f"Image of {mover_id} not found: {image_path}")
                break

            # Convert PIL Image to torch.Tensor
            transform = torchvision.transforms.ToTensor()
            image_tensor = transform(image)

            if (
                image_tensor.shape[0] != image_shape[0]
                or image_tensor.shape[1] != image_shape[1]
            ):
                break
            # Reshape image tensor to match the expected input shape
            image_tensor = image_tensor.view(1, 1, *(image_tensor.shape))
            image_tensors.append(image_tensor)
        else:
            # Loop finished without break
            # Concatenate over width dimension -> (1, 1, 120, 30)
            x_tensor = torch.cat(image_tensors, dim=2)
            x_tensors.append(x_tensor)
            y_hat_tensors.append(torch.tensor([[group_data["label"].iloc[0]]]))
            mover_ids.append(mover_id)

    x = torch.concat(x_tensors)
    y_hat = torch.concat(y_hat_tensors)
    data_set = torch.utils.data.TensorDataset(x, y_hat)
    return data_set, mover_ids


def get_loaders(
    data_set: torch.utils.data.TensorDataset,
    split: Tuple[float, float] = (0.7, 0.3),
    batch_size: int = 4,
) -> Tuple[torch.utils.data.DataLoader, torch.utils.data.TensorDataset]:
    """
    Splits the data into training and validation data and turns the training data into a data loader.

    Args:
        data_set (TensorDataset): Torch Dataset consisting of (input, output) pairs
        split (Tuple[float, float]): Percentage used for training and validation. Should sum to 1.
        batch_size (int): Batch size used for the training loader.

    Returns: Training data loader and validation dataset
    """

    train_data_set, val_data_set = torch.utils.data.random_split(data_set, split)
    train_loader = torch.utils.data.DataLoader(
        train_data_set, batch_size=batch_size, shuffle=True
    )
    return train_loader, val_data_set
