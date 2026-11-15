from pathlib import Path

import torch
from tokenizers import Tokenizer, models, pre_tokenizers
from transformers import LlamaConfig, LlamaForCausalLM, PreTrainedTokenizerFast


def create_model(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(1)
    vocab = {"[UNK]": 0, "<s>": 1, "</s>": 2, "hello": 3, "world": 4}
    for i in range(5, 32):
        vocab[f"tok{i}"] = i
    tok = Tokenizer(models.WordLevel(vocab, unk_token="[UNK]"))
    tok.pre_tokenizer = pre_tokenizers.Whitespace()
    PreTrainedTokenizerFast(
        tokenizer_object=tok, unk_token="[UNK]", bos_token="<s>", eos_token="</s>"
    ).save_pretrained(path)
    cfg = LlamaConfig(
        vocab_size=32,
        hidden_size=256,
        intermediate_size=512,
        num_hidden_layers=2,
        num_attention_heads=4,
        num_key_value_heads=4,
    )
    LlamaForCausalLM(cfg).half().save_pretrained(path)


if __name__ == "__main__":
    create_model(Path("tiny"))
