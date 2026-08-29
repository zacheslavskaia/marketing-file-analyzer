"""Flask web server for the marketing-file-analyzer."""

from __future__ import annotations

import os

from flask import Flask, jsonify, render_template, request

from analyzer import AnalysisError, analyze

MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB upload cap
ALLOWED_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls"}


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.post("/api/analyze")
    def api_analyze():
        if "file" not in request.files:
            return jsonify({"error": "No file was uploaded."}), 400

        uploaded = request.files["file"]
        if not uploaded or uploaded.filename == "":
            return jsonify({"error": "No file was selected."}), 400

        _, ext = os.path.splitext(uploaded.filename.lower())
        if ext not in ALLOWED_EXTENSIONS:
            return (
                jsonify(
                    {
                        "error": (
                            f"Unsupported file type '{ext or 'unknown'}'. "
                            "Upload a CSV, TSV, or Excel file."
                        )
                    }
                ),
                400,
            )

        data = uploaded.read()
        if not data:
            return jsonify({"error": "The uploaded file is empty."}), 400

        try:
            result = analyze(data, uploaded.filename)
        except AnalysisError as exc:
            return jsonify({"error": str(exc)}), 422

        return jsonify(result.to_dict())

    @app.errorhandler(413)
    def too_large(_exc):
        return jsonify({"error": "File is too large (max 16 MB)."}), 413

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
