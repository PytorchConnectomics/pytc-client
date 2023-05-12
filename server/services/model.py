

def start():
    print("start")
    hf_dataset_identifier = "segments/sidewalk-semantic"

    from datasets import load_dataset

    ds = load_dataset(hf_dataset_identifier)
    ds = ds.shuffle(seed=1)
    ds = ds["train"].train_test_split(test_size=0.2)
    train_ds = ds["train"]
    test_ds = ds["test"]

    import json
    from huggingface_hub import hf_hub_download

    repo_id = f"datasets/{hf_dataset_identifier}"
    filename = "id2label.json"
    id2label = json.load(
        open(hf_hub_download(repo_id=hf_dataset_identifier, filename=filename, repo_type="dataset"), "r"))
    id2label = {int(k): v for k, v in id2label.items()}
    label2id = {v: k for k, v in id2label.items()}

    num_labels = len(id2label)

    from torchvision.transforms import ColorJitter
    from transformers import SegformerFeatureExtractor

    feature_extractor = SegformerFeatureExtractor()
    jitter = ColorJitter(brightness=0.25, contrast=0.25, saturation=0.25, hue=0.1)

    def train_transforms(example_batch):
        images = [jitter(x) for x in example_batch['pixel_values']]
        labels = [x for x in example_batch['label']]
        inputs = feature_extractor(images, labels)
        return inputs

    def val_transforms(example_batch):
        images = [x for x in example_batch['pixel_values']]
        labels = [x for x in example_batch['label']]
        inputs = feature_extractor(images, labels)
        return inputs

    # Set transforms
    train_ds.set_transform(train_transforms)
    test_ds.set_transform(val_transforms)

    from transformers import SegformerForSemanticSegmentation

    pretrained_model_name = "nvidia/mit-b0"
    model = SegformerForSemanticSegmentation.from_pretrained(
        pretrained_model_name,
        id2label=id2label,
        label2id=label2id
    )

    from transformers import TrainingArguments

    epochs = 50
    lr = 0.00006
    batch_size = 2

    hub_model_id = "irfan-noordin/segformer-b0-finetuned-segments-sidewalk-oct-22"

    training_args = TrainingArguments(
        "segformer-b0-finetuned-segments-sidewalk-outputs",
        learning_rate=lr,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        save_total_limit=3,
        evaluation_strategy="steps",
        save_strategy="steps",
        save_steps=20,
        eval_steps=20,
        logging_steps=1,
        eval_accumulation_steps=5,
        load_best_model_at_end=True,
        push_to_hub=True,
        hub_model_id=hub_model_id,
        hub_strategy="end",
        logging_dir="./logs/tensorboard"
    )

    import torch
    from torch import nn
    import evaluate

    metric = evaluate.load("mean_iou")

    def compute_metrics(eval_pred):
        with torch.no_grad():
            logits, labels = eval_pred
            logits_tensor = torch.from_numpy(logits)
            # scale the logits to the size of the label
            logits_tensor = nn.functional.interpolate(
                logits_tensor,
                size=labels.shape[-2:],
                mode="bilinear",
                align_corners=False,
            ).argmax(dim=1)

            pred_labels = logits_tensor.detach().cpu().numpy()
            # currently using _compute instead of compute
            # see this issue for more info: https://github.com/huggingface/evaluate/pull/328#issuecomment-1286866576
            metrics = metric._compute(
                predictions=pred_labels,
                references=labels,
                num_labels=len(id2label),
                ignore_index=0,
                reduce_labels=feature_extractor.do_reduce_labels,
            )

            # add per category metrics as individual key-value pairs
            per_category_accuracy = metrics.pop("per_category_accuracy").tolist()
            per_category_iou = metrics.pop("per_category_iou").tolist()

            metrics.update({f"accuracy_{id2label[i]}": v for i, v in enumerate(per_category_accuracy)})
            metrics.update({f"iou_{id2label[i]}": v for i, v in enumerate(per_category_iou)})

            return metrics

    from transformers import Trainer

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=test_ds,
        compute_metrics=compute_metrics,
    )

    trainer.train()

def stop():
    return {"stop"}


def initialize_tensorboard():
    from tensorboard import program

    tb = program.TensorBoard()
    tb.configure(argv=[None, '--logdir', './logs'])
    url = tb.launch()
    print(f'TensorBoard is running at {url}')
    return str(url)

import os
import signal
import subprocess

def stop_tensorboard():
    # Find the process ID of TensorBoard
    process = subprocess.Popen(['pgrep', '-f', 'tensorboard'], stdout=subprocess.PIPE)
    output, _ = process.communicate()
    pid = output.strip().decode()

    # Kill the TensorBoard process
    if pid:
        os.kill(int(pid), signal.SIGTERM)
        print("TensorBoard stopped.")
    else:
        print("TensorBoard is not currently running.")

if __name__ == "__main__":
    start()