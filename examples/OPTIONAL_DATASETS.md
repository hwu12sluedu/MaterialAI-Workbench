# Optional upstream research datasets

The first MaterialAI Workbench release keeps pyLabFEA source, notebooks and example scripts but omits several large CPFFT/CPFEM JSON datasets from Git history. This keeps the clone small and avoids turning optional research data into a core product dependency.

Download the original datasets from the corresponding directories in the upstream pyLabFEA repository:

- <https://github.com/AHartmaier/pyLabFEA/tree/master/examples/Texture/Data_CPFFT>
- <https://github.com/AHartmaier/pyLabFEA/tree/master/examples/Train_CPFEM>

Place the files back under the same paths when running those specific upstream texture-training examples. MaterialAI Workbench, its quick tests and the product closed loop do not require them.
