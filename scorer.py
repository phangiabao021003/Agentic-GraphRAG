from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    answer_correctness,
)

metrics = [
    faithfulness,
    answer_relevancy,
    answer_correctness,
]