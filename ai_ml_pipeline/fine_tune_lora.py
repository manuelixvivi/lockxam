# ==============================================================================
# SCRIPT FINE-TUNING LLM (LORA/PEFT) UNTUK EQUIGRADE AI
# Dijalankan terpisah di Google Colab / GPU Server (A100 / T4)
# ==============================================================================

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
from trl import SFTTrainer


def main():
    # 1. Load Dataset Hasil Ekspor dari Backend Lockxam (JSONL)
    print("Memuat dataset dari sistem web Equigrade...")
    dataset_path = "dataset_lockxam_export.jsonl"
    try:
        dataset = load_dataset("json", data_files=dataset_path, split="train")
    except Exception as e:
        print(f"Peringatan: {e}")
        print("Pastikan file dataset_lockxam_export.jsonl berada di folder yang sama.")
        return

    # 2. Konfigurasi Quantization (QLoRA 4-bit)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

    # 3. Load Model Dasar
    model_name = "Qwen/Qwen2.5-7B"
    print(f"Mempersiapkan model dasar: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name, quantization_config=bnb_config, device_map="auto"
    )

    # 4. Konfigurasi PEFT / LoRA
    model = prepare_model_for_kbit_training(model)
    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)

    # 5. Parameter Pelatihan
    training_args = TrainingArguments(
        output_dir="./equigrade-lora-model",
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        num_train_epochs=3,
        logging_steps=10,
        optim="paged_adamw_8bit",
        save_strategy="epoch",
        fp16=True,
    )

    # 6. Eksekusi Pelatihan
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        peft_config=lora_config,
        dataset_text_field="text",
        max_seq_length=2048,
        tokenizer=tokenizer,
        args=training_args,
    )

    print("Memulai proses Fine-Tuning model...")
    trainer.train()

    # 7. Simpan Hasil Fine-Tuning
    trainer.model.save_pretrained("equigrade-ai-finetuned-adapter")
    print("Selesai! Adapter disimpan. Siap dideploy.")


if __name__ == "__main__":
    main()
