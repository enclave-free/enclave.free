"""Exercise the installed CPU model graph, including its excluded checkpoint loader."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest


class ModelDependencyContractTest(unittest.TestCase):
    def test_accelerate_checkpoint_loader_is_not_installed(self):
        self.assertIsNone(importlib.util.find_spec("accelerate"))

    def test_local_sentence_transformer_encodes_without_accelerate(self):
        from transformers import BertConfig, BertModel, BertTokenizerFast
        from sentence_transformers import SentenceTransformer
        import numpy as np

        with tempfile.TemporaryDirectory() as directory:
            model_dir = Path(directory)
            BertModel(BertConfig(
                vocab_size=8, hidden_size=8, num_hidden_layers=1,
                num_attention_heads=2, intermediate_size=16,
            )).save_pretrained(model_dir)
            (model_dir / "vocab.txt").write_text(
                "[PAD]\n[UNK]\n[CLS]\n[SEP]\n[MASK]\nhello\nworld\n.\n"
            )
            BertTokenizerFast(vocab_file=str(model_dir / "vocab.txt")).save_pretrained(model_dir)
            model = SentenceTransformer(str(model_dir), device="cpu")
            vectors = model.encode(["hello world", "hello"])
            self.assertEqual(vectors.shape, (2, 8))
            self.assertTrue(np.isfinite(vectors).all())

    def test_pdf_converter_imports_without_standard_extras(self):
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.base_models import InputFormat

        options = PdfPipelineOptions()
        options.do_ocr = False
        options.do_table_structure = False
        converter = DocumentConverter(format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=options),
        })
        self.assertIsNotNone(converter)

    @unittest.skipUnless(
        os.getenv("ENCLAVE_VERIFY_QUALITY_PDF") == "1",
        "Set ENCLAVE_VERIFY_QUALITY_PDF=1 for the release check that downloads layout weights",
    )
    def test_quality_pdf_conversion_without_fallback(self):
        import pymupdf
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.base_models import InputFormat

        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "sample.pdf"
            with pymupdf.open() as document:
                document.new_page().insert_text((72, 72), "Enclave PDF compatibility sample")
                document.save(pdf)
            options = PdfPipelineOptions()
            options.do_ocr = False
            options.do_table_structure = False
            converter = DocumentConverter(format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=options),
            })
            text = converter.convert(pdf).document.export_to_markdown()
            self.assertIn("Enclave PDF compatibility sample", text)


if __name__ == "__main__":
    unittest.main()
