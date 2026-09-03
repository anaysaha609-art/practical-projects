from os import path, walk
import argparse
import ast
import time
import sys
import threading
from typing import Any

import ollama


def process_node(node: Any) -> None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        print(node.name)
    else:
        raise TypeError("expected a function or class definition")


def parse_python_ast(file_path):
    """Uses Abstract Syntax Trees to extract function names, classes, and docs without reading raw lines."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            node = ast.parse(f.read(), filename=file_path)

        summary = f"\n--- Summary of {path.basename(file_path)} ---\n"

        docstring = ast.get_docstring(node)
        if docstring:
            summary += f"Description: {docstring}\n"

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                summary += f" - Function: {item.name}()\n"
            elif isinstance(item, ast.ClassDef):
                summary += f" - Class: {item.name}\n"
                for sub_item in item.body:
                    if isinstance(sub_item, ast.FunctionDef):
                        summary += f"   └── Method: {sub_item.name}()\n"
        return summary
    except Exception as e:
        return None


def extract_project_context(project_path):
    """Scans directory and extracts intelligent codebase blueprints using AST and fast file reading."""
    context = ""
    # Added extra virtual environment folders to block infinite loops
    ignored_dirs = {'.git', 'node_modules', '__pycache__', 'venv', '.venv', 'env', '.idea', 'build', 'dist', 'Library'}
    supported_extensions = ('.py', '.c', '.cpp', '.sql', '.js', '.ts', '.go', '.rs', '.java')

    print(f"🔍 Scanning directory: {project_path}")

    for root, dirs, files in walk(project_path):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for file in files:
            if file.endswith(supported_extensions):
                # SUCCESS: This is the correct home for your live scanner tracking print
                print(f"📄 Found file: {file}")

                file_path = path.join(root, file)

                if file.endswith('.py'):
                    ast_summary = parse_python_ast(file_path)
                    if ast_summary:
                        context += ast_summary
                        continue

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        relative_path = path.relpath(file_path, project_path)
                        context += f"\n--- File: {relative_path} ---\n{f.read()[:1500]}\n"
                except Exception as e:
                    print(f"⚠️ Could not read {file}: {e}")

    return context


def loading_animation(stop_event):
    chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    idx = 0
    sys.stdout.write("🧠 Analyzing codebase with Llama 3.2 offline ")
    while not stop_event.is_set():
        sys.stdout.write(f"\r🧠 Analyzing codebase with Llama 3.2 offline {chars[idx % len(chars)]}")
        sys.stdout.flush()
        idx += 1
        time.sleep(0.1)
    sys.stdout.write("\r🧠 Analysis and rendering complete!            \n")
    sys.stdout.flush()


def get_user_metadata():
    # Highlighted Fix: Quick y/n toggle
    choice = input("\n🛠️  Do you want to enter custom project metadata? (y/n): ").strip().lower()
    if choice not in ['y', 'yes', '']:
        print("⏩ Skipping interactive setup. Using default/inferred metadata.")
        return {"name": "", "author": "", "license": "MIT", "notes": ""}

    print("\n--- 🛠️  Interactive Configuration ---")
    project_name = input("📦 Project Name: ").strip()
    author = input("👤 Author Name/GitHub Handle: ").strip()
    license_type = input("📄 License (e.g., MIT, Apache 2.0): ").strip() or "MIT"
    special_notes = input("💡 Any custom notes/features to highlight?: ").strip()

    return {"name": project_name, "author": author, "license": license_type, "notes": special_notes}



def generate_markdown(code_context, meta):
    meta_instruction = f"""
    Custom metadata to include:
    - Project Name: {meta['name'] if meta['name'] else 'Infer from code'}
    - Author: {meta['author'] if meta['author'] else 'Not specified'}
    - License: {meta['license']}
    - Extra User Notes: {meta['notes'] if meta['notes'] else 'None'}
    """

    system_prompt = (
        "You are an elite technical writer. Analyze the provided codebase overview and metadata to generate "
        "a highly professional, beautiful README.md file. Use clean Markdown elements, visual anchors, "
        "and clear headers. Include sections for: Project Overview, Core Architecture/Features, "
        "Tech Stack, Setup Instructions, How to Use It (with clear terminal command examples like in mac,windows,linux especially etc.), and License. "
        "Output ONLY the raw markdown text. Do not include any casual chat or intro/outro text like 'Here is your README'."
    )

    stop_loading = threading.Event()
    spinner_thread = threading.Thread(target=loading_animation, args=(stop_loading,))
    spinner_thread.start()

    try:
        response = ollama.generate(
            model='llama3.2',
            prompt=f"{system_prompt}\n{meta_instruction}\n\nCodebase Context:\n{code_context}"
        )
        stop_loading.set()
        spinner_thread.join()
        return response['response']
    except Exception as e:
        stop_loading.set()
        spinner_thread.join()
        print(f"❌ Ollama Error: Ensure Ollama app is running locally. Details: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Local-README: An offline AI-powered README.md framework.")
    parser.add_argument('-d', '--dir', type=str, default='.', help='Path to project directory')
    parser.add_argument('-o', '--output', type=str, default='.', help='Path to save README.md')
    parser.add_argument('-i', '--interactive', action='store_true', help='Enable interactive metadata mode')

    args = parser.parse_args()
    target_dir = path.abspath(args.dir)
    output_dir = path.abspath(args.output)

    context = extract_project_context(target_dir)
    if not context.strip():
        print("❌ Error: No valid code files found to analyze in this directory.")
        return

    meta = get_user_metadata() if args.interactive else {"name": "", "author": "", "license": "MIT", "notes": ""}
    readme_content = generate_markdown(context, meta)

    if readme_content:
        output_file_path = path.join(output_dir, "README.md")
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write(readme_content)
        print(f"🎉 Success! Local-README saved your file to: {output_file_path}")


# This execution block must be the absolute end of the file.
if __name__ == "__main__":
    main()
