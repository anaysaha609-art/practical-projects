from os import makedirs, path, walk
import argparse
import ast
import sys
import threading
import time
from typing import Any

try:
    import ollama
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    ollama = None


def process_node(node: Any) -> str:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    raise TypeError("expected a function or class definition")


class CodebaseVisitor(ast.NodeVisitor):
    """Recursive AST visitor for reporting classes and functions."""

    def __init__(self):
        self.output_lines = []
        self._indent_level = 0

    def visit_FunctionDef(self, node: ast.FunctionDef):
        indent = "   " * self._indent_level
        prefix = "└── Method: " if self._indent_level > 0 else " - Function: "
        self.output_lines.append(f"{indent}{prefix}{node.name}()")
        self._indent_level += 1
        self.generic_visit(node)
        self._indent_level -= 1

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        indent = "   " * self._indent_level
        prefix = "└── Async Method: " if self._indent_level > 0 else " - Async Function: "
        self.output_lines.append(f"{indent}{prefix}{node.name}()")
        self._indent_level += 1
        self.generic_visit(node)
        self._indent_level -= 1

    def visit_ClassDef(self, node: ast.ClassDef):
        indent = "   " * self._indent_level
        self.output_lines.append(f"{indent} - Class: {node.name}")
        self._indent_level += 1
        self.generic_visit(node)
        self._indent_level -= 1


def parse_python_ast(file_path):
    """Extract class/function summaries and docstrings using Python's AST."""
    try:
        with open(file_path, "r", encoding="utf-8") as file_obj:
            root_node = ast.parse(file_obj.read(), filename=file_path)

        summary = f"\n--- Summary of {path.basename(file_path)} ---\n"

        docstring = ast.get_docstring(root_node)
        if docstring:
            summary += f"Description: {docstring}\n"

        visitor = CodebaseVisitor()
        visitor.visit(root_node)
        if visitor.output_lines:
            summary += "\n".join(visitor.output_lines) + "\n"
        return summary
    except (FileNotFoundError, PermissionError) as exc:
        sys.stderr.write(f"❌ OS Security/File IO Exception on {file_path}: {exc}\n")
        return None
    except SyntaxError as exc:
        sys.stderr.write(f"⚠️ Syntax compilation exception parsing AST for {file_path}: {exc}\n")
        return None


def read_file_safely(file_path, max_lines=50):
    """Read a bounded preview from a file without truncating mid-line."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as file_obj:
            lines = []
            for _ in range(max_lines):
                line = file_obj.readline()
                if not line:
                    break
                lines.append(line)
            return "".join(lines)
    except (FileNotFoundError, PermissionError) as exc:
        sys.stderr.write(f"❌ Read failure stream boundary on {file_path}: {exc}\n")
        return ""


def extract_project_context(project_path):
    """Scan a target path and collect source-context snippets for README generation."""
    context = ""
    ignored_dirs = {'.git', 'node_modules', '__pycache__', 'venv', '.venv', 'env', '.idea', 'build', 'dist', 'Library'}
    supported_extensions = ('.py', '.c', '.cpp', '.sql', '.js', '.ts', '.go', '.rs', '.java')

    if not path.exists(project_path):
        print(f"❌ Error: Path does not exist: {project_path}")
        return ""

    if path.isfile(project_path):
        if project_path.endswith(supported_extensions):
            print(f"📄 Found single target file: {path.basename(project_path)}")
            if project_path.endswith('.py'):
                ast_summary = parse_python_ast(project_path)
                if ast_summary:
                    return ast_summary

            file_content = read_file_safely(project_path)
            if file_content:
                return f"\n--- File: {path.basename(project_path)} ---\n{file_content}\n"
        return ""

    print(f"🔍 Scanning directory: {project_path}")
    for root, dirs, files in walk(project_path):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for file in files:
            if not file.endswith(supported_extensions):
                continue

            print(f"📄 Found file: {file}")
            file_path = path.join(root, file)

            if file.endswith('.py'):
                ast_summary = parse_python_ast(file_path)
                if ast_summary:
                    context += ast_summary
                    continue

            file_content = read_file_safely(file_path)
            if file_content:
                relative_path = path.relpath(file_path, project_path)
                context += f"\n--- File: {relative_path} ---\n{file_content}\n"

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
    choice = input("\n🛠️  Do you want to enter custom project metadata? (y/n): ").strip().lower()
    if choice not in {'y', 'yes', ''}:
        print("⏩ Skipping interactive setup. Using default/inferred metadata.")
        return {"name": "", "author": "", "license": "MIT", "notes": ""}

    print("\n--- 🛠️  Interactive Configuration (Press enter to Skip) ---")
    project_name = input("📦 Project Name: ").strip()
    author = input("👤 Author Name/GitHub Handle: ").strip()
    license_type = input("📄 License (e.g., MIT, Apache 2.0): ").strip() or "MIT"
    special_notes = input("💡 Any custom notes/features to highlight?: ").strip()

    return {"name": project_name, "author": author, "license": license_type, "notes": special_notes}


def generate_markdown(code_context, meta):
    if ollama is None:
        print("❌ Ollama library is not installed. Install it with: pip install ollama")
        return None

    meta_instruction = f"""
    Custom metadata to include:
    - Project Name: {meta['name'] if meta['name'] else 'Infer from code'}
    - Author: {meta['author'] if meta['author'] else 'Not specified'}
    - License: {meta['license']}
    - Extra User Notes: {meta['notes'] if meta['notes'] else 'None'}
    """

    system_prompt = (
        "You are a strict, precise principal systems engineer. Analyze the provided codebase context and project metadata "
        "to generate an authentic, accurate README.md file. Do not invent details.\n\n"
        "STRICT COMPLIANCE RULES:\n"
        "1. NO HALLUCINATIONS: Do not mention files like 'install.py', 'generator.py.exe', or 'nltk'. They do not exist in this project. "
        "Only reference the actual codebase provided in the context.\n"
        "2. ACCURATE COMMAND LINE FLAGS: Look directly at the argparse configuration in the code. Document ONLY the actual active flags: "
        "'-d/--dir' for path input, '-o/--output' for output location, and '-i/--interactive' for enabling user configuration.\n"
        "3. ACTUAL TECH STACK: Clearly state that the tool runs locally and offline using Python 3, the native 'ast' module for parsing, "
        "the 'threading' module for a non-blocking terminal animation loop, and the local 'ollama' Python library running a 'llama3.2' model.\n"
        "4. SYSTEM ARCHITECTURE: Explain that the script uses Abstract Syntax Tree (AST) parsing to deterministically scan classes, "
        "functions, and docstrings from python compilation units without running unsafe code, before piping the clean blueprint context to the offline model.\n\n"
        "Structure the output with clean markdown headers: # Project Name, ## System Architecture, ## Technical Stack, ## Installation & Environment Setup, ## Usage Guide, and ## Open-Source License."
    )

    stop_loading = threading.Event()
    spinner_thread = threading.Thread(target=loading_animation, args=(stop_loading,), daemon=True)
    spinner_thread.start()

    try:
        response = ollama.generate(
            model='llama3.2',
            prompt=f"{system_prompt}\n{meta_instruction}\n\nCodebase Context:\n{code_context}",
            options={
                "temperature": 0.0,
                "top_p": 0.1,
            },
        )
        return response['response']
    except Exception as exc:
        print(f"❌ Ollama Error: Ensure Ollama app is running locally. Details: {exc}")
        return None
    finally:
        stop_loading.set()
        spinner_thread.join(timeout=1.0)


def run_interactive_chatbot(model_name="llama3.2", max_memory_size=10):
    """Launch a local terminal chatbot using a bounded memory window."""
    if ollama is None:
        print("❌ Ollama library is not installed. Install it with: pip install ollama")
        return

    log_dir = ".ai_chat_history"
    makedirs(log_dir, exist_ok=True)
    log_file_path = path.join(log_dir, f"session_{int(time.time())}.txt")

    memory_buffer = [{"role": "system", "content": "You are a highly capable AI software assistant. Answer directly and cleanly."}]

    print("\n=============================================================")
    print("🧠 LOCAL TERMINAL AI CHATBOT RUNTIME ENGAGED (SLIDING WINDOW) 🧠")
    print(f"🔒 Session logs writing to: {log_file_path}")
    print("⌨️  Type 'exit', 'quit', or 'clear' to manage runtime loops.")
    print("=============================================================\n")

    while True:
        try:
            user_input = input("👤 You: ").strip()
            if not user_input:
                continue

            if user_input.lower() in {"exit", "quit"}:
                print("\n🛑 Terminating local chat container loop safely. System exit code: 0.")
                break

            if user_input.lower() == "clear":
                memory_buffer = [memory_buffer[0]]
                print("🧹 Conversation memory window cleared successfully.\n")
                continue

            memory_buffer.append({"role": "user", "content": user_input})

            if len(memory_buffer) > max_memory_size:
                memory_buffer = [memory_buffer[0]] + memory_buffer[-(max_memory_size - 1):]

            print("🤖 AI Engine: Thinking...", end="", flush=True)
            response = ollama.chat(model=model_name, messages=memory_buffer)
            ai_reply = response["message"]["content"]
            print("\r" + " " * 30 + "\r")
            print(f"🤖 AI Engine:\n{ai_reply}\n")

            memory_buffer.append({"role": "assistant", "content": ai_reply})
            if len(memory_buffer) > max_memory_size:
                memory_buffer = [memory_buffer[0]] + memory_buffer[-(max_memory_size - 1):]

            with open(log_file_path, "a", encoding="utf-8") as history_log:
                history_log.write(f"User: {user_input}\nAssistant: {ai_reply}\n\n")

        except KeyboardInterrupt:
            print("\n🛑 Session interrupted by user. Exiting chatbot.")
            break
        except Exception as exc:
            print(f"\n❌ Local chatbot exception encountered: {exc}\n")
            break


def main():
    parser = argparse.ArgumentParser(description="Local-README & Dev Assistant Suite.")
    parser.add_argument('-d', '--dir', type=str, default='.', help='Path to project directory or specific file')
    parser.add_argument('-o', '--output', type=str, default='.', help='Path to save README.md')
    parser.add_argument('-i', '--interactive', action='store_true', help='Enable interactive metadata mode')
    parser.add_argument('-c', '--chat', action='store_true', help='Launch the Local AI Terminal Chatbot container mode')

    args = parser.parse_args()

    if args.chat:
        run_interactive_chatbot()
        return

    target_path = path.abspath(args.dir)
    output_dir = path.abspath(args.output)

    if not path.exists(target_path):
        print(f"❌ Error: No valid path found at {target_path}")
        return

    context = extract_project_context(target_path)
    if not context.strip():
        print("❌ Error: No valid code files found to analyze at this path.")
        return

    if path.isdir(output_dir) or (not path.exists(output_dir) and not path.splitext(output_dir)[1]):
        output_file_path = path.join(output_dir, "README.md")
    else:
        output_file_path = output_dir

    parent_dir = path.dirname(output_file_path)
    if parent_dir and not path.exists(parent_dir):
        makedirs(parent_dir, exist_ok=True)

    if path.exists(output_file_path):
        print(f"\n⚠️  CRITICAL WARNING: A documentation file already exists at:\n    {output_file_path}")
        confirm = input("💥 Do you want to overwrite this file? This action cannot be undone! (y/n): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("🛑 Execution aborted safely. Existing file preserved. Goodbye!")
            return

    meta = get_user_metadata() if args.interactive else {"name": "", "author": "", "license": "MIT", "notes": ""}
    readme_content = generate_markdown(context, meta)

    if readme_content:
        with open(output_file_path, "w", encoding="utf-8") as output_file:
            output_file.write(readme_content)
        print(f"🎉 Success! Local-README saved your file to: {output_file_path}")


if __name__ == "__main__":
    main()
