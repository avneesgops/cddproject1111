"""Fine-tune XLM-R on multilingual claim/evidence pairs (local, no paid API)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from datasets import Dataset
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "datasets" / "verification"
LABELS = ["SUPPORTED", "REFUTED", "MIXED", "NOT_ENOUGH_EVIDENCE"]
LABEL_TO_ID = {label: i for i, label in enumerate(LABELS)}


def frame_dataset(frame: pd.DataFrame, tokenizer, max_length: int) -> Dataset:
    frame = frame[frame.label.isin(LABEL_TO_ID)].copy()
    ds = Dataset.from_pandas(frame[["claim", "evidence", "label"]], preserve_index=False)

    def tokenize(batch):
        encoded = tokenizer(batch["claim"], batch["evidence"], truncation="only_second", max_length=max_length)
        encoded["labels"] = [LABEL_TO_ID[label] for label in batch["label"]]
        return encoded

    return ds.map(tokenize, batched=True, remove_columns=ds.column_names)


def metrics_for(eval_prediction):
    logits, labels = eval_prediction
    predicted = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, predicted),
        "macro_f1": f1_score(labels, predicted, labels=list(range(len(LABELS))), average="macro", zero_division=0),
    }


class WeightedTrainer(Trainer):
    """Use inverse-frequency class weights so common ratings do not dominate."""
    def __init__(self, *args, class_weights=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        loss_fn = torch.nn.CrossEntropyLoss(weight=self.class_weights.to(outputs.logits.device))
        loss = loss_fn(outputs.logits, labels)
        return (loss, outputs) if return_outputs else loss


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="FacebookAI/xlm-roberta-base")
    parser.add_argument("--output", default=str(ROOT / "models" / "xlmr_claim_verifier"))
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=384)
    args = parser.parse_args()

    train_frame = pd.read_csv(DATA / "train.csv", dtype=str).fillna("")
    validation_frame = pd.read_csv(DATA / "validation.csv", dtype=str).fillna("")
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    label2id = {label: i for i, label in enumerate(LABELS)}
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model, num_labels=len(LABELS), label2id=label2id,
        id2label={i: label for label, i in label2id.items()},
    )
    train_ds = frame_dataset(train_frame, tokenizer, args.max_length)
    validation_ds = frame_dataset(validation_frame, tokenizer, args.max_length)
    counts = train_frame.label.value_counts().reindex(LABELS, fill_value=1).to_numpy(dtype=np.float32)
    class_weights = torch.tensor(counts.sum() / (len(LABELS) * counts), dtype=torch.float32)
    training_args = TrainingArguments(
        output_dir=args.output,
        learning_rate=2e-5,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        num_train_epochs=args.epochs,
        weight_decay=0.01,
        warmup_ratio=0.06,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        save_total_limit=2,
        logging_steps=100,
        report_to="none",
        seed=42,
        data_seed=42,
        fp16=torch.cuda.is_available(),
    )
    trainer = WeightedTrainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=validation_ds,
        data_collator=DataCollatorWithPadding(tokenizer),
        processing_class=tokenizer,
        compute_metrics=metrics_for,
        class_weights=class_weights,
    )
    trainer.train()
    trainer.save_model(args.output)
    tokenizer.save_pretrained(args.output)

    reports = {"model": args.model, "labels": LABELS, "splits": {}}
    split_files = {
        "x_fact_in_domain": "in_domain_test.csv",
        "x_fact_new_sites": "out_of_domain_test.csv",
        "x_fact_zero_shot_languages": "zero_shot_test.csv",
    }
    for name, filename in split_files.items():
        frame = pd.read_csv(DATA / filename, dtype=str).fillna("")
        prediction = trainer.predict(frame_dataset(frame, tokenizer, args.max_length))
        reports["splits"][name] = {
            **metrics_for((prediction.predictions, prediction.label_ids)),
            "rows": len(frame), "languages": int(frame.language.nunique()),
        }
    reports["validation"] = trainer.evaluate(validation_ds)
    report_path = Path(args.output) / "evaluation.json"
    report_path.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
