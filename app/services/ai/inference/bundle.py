from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.services.ai.training.registry.artifact_builder import ModelArtifactBuilder
from app.services.ai.training.registry.schemas import (
    FileChecksum,
    IntegrityVerificationResult,
)


class ServingExecutionContract(BaseModel):
    """
    Contract defining runtime serving requirements and execution metadata for an InferenceBundle.
    """

    model_config = ConfigDict(frozen=True)

    max_sequence_length: int = Field(default=2048, description="Maximum context window tokens")
    temperature: float = Field(
        default=0.0, description="Sampling temperature (deterministic for grading)"
    )
    top_p: float = Field(default=1.0, description="Nucleus sampling threshold")
    enable_rag_augmentation: bool = Field(
        default=False, description="Flag indicating if RAG context injection is evaluated"
    )


@dataclass(frozen=True)
class InferenceBundle:
    """
    Milestone A9.4.4: Immutable Inference Model Bundle.
    Encapsulates verified PEFT adapter weights, dynamic base model provenance,
    tokenizer metadata, and cryptographic integrity proof for production serving.
    RAG vector retrieval remains strictly decoupled from this model weights bundle.
    """

    model_name: str
    version: str
    version_number: int
    status: str
    base_model_name: str
    base_model_revision: Optional[str]
    tokenizer_name_or_path: str
    adapter_type: str
    adapter_dir: str
    artifact_manifest_hash: str
    file_manifest: List[FileChecksum]
    contract: ServingExecutionContract = field(default_factory=ServingExecutionContract)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def verify_integrity(self) -> IntegrityVerificationResult:
        """
        Executes real-time cryptographic verification on the local adapter directory.
        Protects serving runtime against bit-rot, missing weights, and file tampering.
        """
        return ModelArtifactBuilder.verify_artifact_integrity(
            artifact_dir=self.adapter_dir,
            expected_manifest_hash=self.artifact_manifest_hash,
            expected_file_manifest=self.file_manifest,
        )

    def format_inference_prompt(
        self, user_instruction: str, student_answer: str, rubric_criteria: str
    ) -> str:
        """
        Constructs canonical evaluation input prompt format matching the SFT training contract.
        """
        return (
            f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
            f"{user_instruction}\n\n"
            f"Rubrik Penilaian:\n{rubric_criteria}<|eot_id|>\n"
            f"<|start_header_id|>user<|end_header_id|>\n"
            f"Jawaban Siswa:\n{student_answer}<|eot_id|>\n"
            f"<|start_header_id|>assistant<|end_header_id|>\n"
        )
