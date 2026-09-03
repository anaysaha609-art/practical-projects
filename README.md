# Infer
## System Architecture

Infer is a Python-based tool that runs locally and offline, utilizing the native `ast` module for parsing Abstract Syntax Tree (AST) representations of Python compilation units. The script employs a non-blocking terminal animation loop facilitated by the `threading` module to provide an interactive user experience.

The tool's core functionality involves deterministic scanning of classes, functions, and docstrings from Python files without executing unsafe code. This is achieved through AST parsing, which allows for precise analysis and extraction of relevant project context.

The offline model, powered by the local 'ollama' library running a 'llama3.2' model, processes the clean blueprint context generated from the parsed AST to produce meaningful insights or recommendations.

## Technical Stack

Infer relies on the following technical components:

*   Python 3: The primary programming language used for development and execution.
*   `ast` module: Utilized for parsing Abstract Syntax Tree representations of Python compilation units.
*   `threading` module: Facilitates a non-blocking terminal animation loop to enhance user interaction.
*   'ollama' library: Powers the offline model, leveraging a pre-trained 'llama3.2' model for context analysis and recommendations.

## Installation & Environment Setup

To utilize Infer, follow these steps:

1.  Install Python 3 on your system if not already present.
2.  Ensure the necessary libraries are installed:
    *   `ast` module: Part of the standard library in Python 3.
    *   'ollama' library: Can be installed via pip using the command `pip install ollama`.
3.  Set up a suitable environment for Infer to operate within.

## Usage Guide

### Command Line Flags

Infer accepts the following command line flags:

*   `-d/--dir`: Specifies the path to the directory containing Python files to analyze.
*   `-o/--output`: Defines the output location for the generated insights or recommendations.
*   `-i/--interactive`: Enables user configuration and interactive mode.

### Usage Example

```bash
python infer.py -d /path/to/project -o /path/to/output -i
```

## Open-Source License

Infer is licensed under the MIT license.