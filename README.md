# 🛡️ Automated Scalable And Programmable Framework For Post-Silicon Security Remediation

## 📦 Dependencies

- 🎨 **ASCII GUI** with `Tkinter` & `PyFiglet`
- 🧠 **Verilog Parser** with `PyVerilog`
- 🔍 **Lexical Analyzer** using `ply`

---

## 💻 Installation (macOS & Linux)

Follow these steps in your terminal:

---

### 1. ✅ Install Python (if not already installed)

- **macOS:**

  ```bash
  brew install python
  ```

- **Linux (Ubuntu/Debian):**

  ```bash
  sudo apt update
  sudo apt install python3 python3-pip
  ```

---

### 2. 🪟 Install `tkinter` (GUI Library)

- **macOS (Homebrew Python only):**

  ```bash
  brew install python-tk
  ```

- **Linux:**

  ```bash
  sudo apt install python3-tk
  ```

---

### 3. 📦 Install Required Python Packages

```bash
pip3 install pyfiglet pyverilog ply
```

> Optional (for legacy Python < 3.4):
>
> ```bash
> pip3 install enum34
> ```

---

## 🚀 Running the ASAP Tool

To launch the tool:

```bash
cd src/
python3 ASAPGuiWrapper.py
```

This will open a GUI interface like the one below:

<img width="877" alt="ASAP GUI" src="https://github.com/user-attachments/assets/ebbaeb79-d53a-4405-9b5e-b2622a1f1f68" />

---

## 🧭 GUI Drop-down Menu Options

### 1. 🔧 ASAP Insertion

Use during the **pre-silicon design phase** to insert logic hooks into your RTL source files based on pragma annotations.

**Inputs required:**

- **Specification file:**  
  Example: `src/asap_params.spec`

- **Output directory:**  
  Where modified RTL files will be written.

---

### 2. 🛠️ ASAP Compiler

Compiles patch programs and generates bitstream files to program the ASAP patch architecture.

**Inputs required:**

- **Specification file:**  
  Example: `src/asap_params.spec`

- **Output folder:**  
  Where bitstreams will be saved.

- **Interface file:**  
  Generated during ASAP Insertion; contains observed/controlled signals.

- **SRU program file:**  
  SRU patch logic. Examples in `asap_sample/remediation_programs/`

- **SMU program file:**  
  SMU patch logic. Examples in `asap_sample/remediation_programs/`

---

## 🧪 Patch Simulation

The ASAP Compiler will generate:

- `patch.asap.smu`
- `patch.asap.sru`

These bitstreams are streamed into the `asapTop` top-level module generated during ASAP Insertion.

🧪 Sample testbenches for simulation are available in:

```
asap_sample/tests/
```

---

## 📝 Tips

- On **Apple Silicon Macs**, install developer tools if you hit build issues:

  ```bash
  xcode-select --install
  ```

- On **Linux**:

  ```bash
  sudo apt install build-essential python3-dev
  ```

---


## 🔗 External References

- [PyVerilog on GitHub](https://github.com/PyHDI/PyVerilog)
- [PLY Documentation](http://www.dabeaz.com/ply/)
- [pyfiglet on PyPI](https://pypi.org/project/pyfiglet/)
