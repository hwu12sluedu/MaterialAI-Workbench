# API 功能清单（自动生成）

> 本文件由 `tools/generate_api_inventory.py` 生成，用于保证教学文档覆盖全部公开函数与类。修改源码后重新运行脚本即可刷新。

## 统计

- 模块数：52
- 顶层公开函数：234
- 公开类：61
- 公开类方法：89

## 使用方式

```powershell
conda run -n pylabfea python tools/generate_api_inventory.py
```

## `pylabfea.__init__`

- 文件：`src/pylabfea/__init__.py`
- 模块说明：Top-level package for pyLabFEA

## `pylabfea.basic`

- 文件：`src/pylabfea/basic.py`
- 模块说明：Module pylabfea.basic introduces basic methods and attributes like calculation of

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `sig_hydro(sig)` | 39 | 待补充 |
| `sig_eq_j2(sig: np.ndarray)` | 49 | Calculate sj2 equivalent stress from any stress tensor |
| `sig_polar_ang(sig: np.ndarray)` | 87 | Transform stresses into polar angle on deviatoric plane spanned by a_vec and b_vec |
| `sig_princ(sig: np.ndarray)` | 126 | Convert Voigt stress tensors into principal stresses and eigenvectors. |
| `sig_cyl2princ(s_cyl)` | 203 | Convert cylindrical stress into 3D Cartesian principle stress |
| `sig_cyl2voigt(sig_cyl: np.ndarray, eigen_vector: np.ndarray)` | 232 | Convert cylindrical stress and eigenvectors into Voigt stress tensor |
| `sig_princ2cyl(sig: np.ndarray, mat = None)` | 257 | Convert principal stress into cylindrical stress vector |
| `sig_spherical_to_cartesian(angles, seq = 1.0)` | 301 | Convert a list of 5 spherical angles to a Voigt stress tensor. |
| `sig_dev(sig: np.ndarray)` | 325 | Calculate deviatoric stress component from given stress tensor |
| `eps_eq(eps: np.ndarray)` | 349 | Calculate equivalent strain |
| `pickle2mat(name, path = './')` | 569 | Read pickled material file. |
| `seq_J2(sig)` | 600 | 待补充 |
| `sprinc(sig)` | 604 | 待补充 |
| `sp_cart(scyl)` | 608 | 待补充 |
| `svoigt(scyl, evec)` | 612 | 待补充 |
| `s_cyl(sig, mat = None)` | 616 | 待补充 |
| `sdev(sig)` | 620 | 待补充 |
| `polar_ang(sig)` | 624 | 待补充 |

### 类与方法

#### `Stress(object)`

- 行号：387
- 说明：Stores and converts Voigt stress tensors into different formats,

| 方法 | 行号 | 说明 |
|---|---:|---|
| `seq(self, mat = None)` | 424 | calculate Hill-type equivalent stress, invokes corresponding method of class ``Material`` |
| `theta(self)` | 445 | Calculate polar angle in deviatoric plane |
| `seq_j2(self)` | 456 | Calculate J2 principal stress |
| `cyl(self)` | 467 | Calculate cylindrical stress tensor |
| `lode_ang(self, arg)` | 478 | Calculate Lode angle: |

#### `Strain(object)`

- 行号：508
- 说明：Stores and converts Voigt strain tensors into different formats,

| 方法 | 行号 | 说明 |
|---|---:|---|
| `eeq(self)` | 541 | Calculate equivalent strain |
| `inv(self)` | 552 | Calculate inverse of strain tensor ignoring zeros. |


## `pylabfea.data`

- 文件：`src/pylabfea/data.py`
- 模块说明：Module pylabfea.data introduces the class ``Data`` for handling of data resulting

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `ln_strain(eng_strain)` | 29 | 待补充 |
| `eng_strain(ln_strain)` | 37 | 待补充 |
| `interpolate_stress(s0, s1, e0, e1, et)` | 41 | 待补充 |
| `find_transition_index(stress)` | 45 | Calculates the index at which a significant transition in the total stress-strain relationship occurs. |
| `get_elastic_coefficients(eps, sig, method = 'least_square', initial_guess = None)` | 84 | A function to compute the elastic coefficients (stiffness matrix) for a material |

### 类与方法

#### `Data(object)`

- 行号：351
- 说明：Define class for handling data from virtual mechanical tests in micromechanical

| 方法 | 行号 | 说明 |
|---|---:|---|
| `key_parser(self, key)` | 471 | 待补充 |
| `add_data(self, data_file: str, path_data = './')` | 486 | 待补充 |
| `write_info(self, data: dict)` | 492 | 待补充 |
| `read_data(self, data_File: str)` | 500 | Read database in form of JSON file and convert it into a dictionary containing stress and strain |
| `parse_data(self, epl_crit, epl_start, epl_max, depl)` | 706 | Read data and store in attribute 'mat_data' |
| `convert_data(self, sig)` | 890 | Convert data provided only for stress tensor at yield point into mat_data dictionary |
| `add2mat_data(self, data_dict, key)` | 916 | 待补充 |
| `plot_training_data(self, emax = 1)` | 925 | 待补充 |
| `plot_data(self, data, xlabel, ylabel, emax = None)` | 931 | 待补充 |
| `plot_stress_strain(self, plot_peeq = True, eps_max = 0.1, epc = None, fontsize = 14, cmap = 'viridis')` | 943 | 待补充 |
| `plot_yield_stress(self, show_hist = True, test_data = None, fontsize = 14, cmap = 'viridis')` | 975 | 待补充 |
| `plot_set(self)` | 1008 | 待补充 |
| `plot_yield_locus(self, db, mat_data, active, scatter = False, data = None, data_label = None, arrow = False, file = None, title = None, fontsize = 18)` | 1057 | 待补充 |


## `pylabfea.gui`

- 文件：`src/pylabfea/gui.py`

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `self_closing_message(message, duration = 4000)` | 11 | Display a self-closing message box. |
| `add_label_and_entry(frame, row, label_text, entry_var, entry_type = 'entry', bold = True, options = None)` | 38 | 待补充 |

### 类与方法

#### `UserInterface(object)`

- 行号：56

| 方法 | 行号 | 说明 |
|---|---:|---|
| `close(self)` | 104 | 待补充 |
| `display_plot(self, fig)` | 108 | Show image on canvas. |
| `run(self)` | 124 | 待补充 |


## `pylabfea.material`

- 文件：`src/pylabfea/material.py`
- 模块说明：Module pylabfea.material introduces class ``Material`` that contains attributes and methods

### 类与方法

#### `Material(object)`

- 行号：68
- 说明：Define class for Materials including material parameters (attributes), constitutive relations (methods)

| 方法 | 行号 | 说明 |
|---|---:|---|
| `response(self, sig, epl, deps, CV, maxit = 50)` | 218 | Calculate non-linear material response to deformation defined by load step, |
| `calc_yf(self, sig, epl = None, accumulated_strain = 0.0, max_stress = 0.0, flag = 0.0, tex = None, ana = False, pred = False)` | 359 | Calculate yield function |
| `ML_full_yf(self, sig, epl = None, ld = None, accumulated_strain = 0.0, max_stress = 0.0, flag = 0.0, tex = None, verb = True)` | 425 | Calculate full ML yield function as distance of a single given stress |
| `find_yloc(self, x, su, epl = None, accumulated_strain = 0.0, max_stress = 0.0, flag = 0.0, tex = None)` | 529 | Function to expand unit stresses by factor and calculate yield |
| `find_yloc_scalar(self, x, su, epl = None, accumulated_strain = 0.0, max_stress = 0.0, flag = 0.0, tex = None)` | 558 | Function to expand unit stresses by factor and calculate yield |
| `calc_seq(self, sig)` | 587 | Calculate generalized equivalent stress from stress tensor; |
| `calc_seqB(self, sv)` | 689 | Calculate equivalent stress based on Yld2004-18p yield function |
| `calc_fgrad(self, sig, epl = None, seq = None, accumulated_strain = 0.0, max_stress = 0.0, flag = 0.0, tex = None, ana = False)` | 719 | Calculate gradient to yield surface. Three different methods can be used: (i) analytical gradient to Hill-like yield |
| `calc_hessian(self, sig, epl = None, seq = None, accumulated_strain = 0.0, max_stress = 0.0, flag = 0.0, tex = None, ana = False)` | 875 | Calculate hessian to yield surface. Supports so far only option (ii) hessian to ML yield function (default if ML yield |
| `get_sflow(self, epl)` | 989 | Calculate an estimate of the scalar flow stress (strength) of the material |
| `epl_dot(self, sig, epl, Cel, deps, accumulated_strain = 0.0, max_stress = 0.0, flag = 0.0, tex = None)` | 1024 | Calculate plastic strain increment relaxing stress back to yield locus; |
| `C_tan(self, sig, Cel, epl = None)` | 1072 | Calculate tangent stiffness relaxing stress back to yield locus; |
| `setup_yf_SVM(self, x, y_train, x_test = None, y_test = None, C = 15.0, gamma = 2.5, fs = 0.1, plot = False, cyl = False, gridsearch = False, cvals = None, gvals = None, verbose = 3)` | 1106 | Generic function call to setup and train the SVM yield function, for details see the specific functions |
| `setup_yf_SVM_6D(self, x, y_train, x_test = None, y_test = None, C = 10.0, gamma = 1.0, plot = False, gridsearch = False, cvals = None, gvals = None, verbose = 3, pca_dim = 10, metric = 'acc')` | 1124 | Initialize and train Support Vector Classifier (SVC) as machine learning (ML) yield function. Training and |
| `setup_yf_SVM_3D(self, x, y_train, x_test = None, y_test = None, C = 10.0, gamma = 1.0, fs = 0.1, plot = False, cyl = False, gridsearch = False, cvals = None, gvals = None, pca_dim = 10)` | 1295 | Initialize and train Support Vector Classifier (SVC) as machine |
| `train_SVC(self, C = 10, gamma = 4, Nlc = 36, Nseq = 25, fs = 0.3, extend = False, mat_ref = None, sdata = None, plot = False, fontsize = 16, gridsearch = False, cvals = None, gvals = None, Fe = 0.1, Ce = 0.99, scaler = None, pca = None, train_index = None, test_index = None, verbose = 1, metric = 'acc', pca_dim = 10, reversal = None)` | 1457 | Train SVC for all yield functions of the microstructures provided |
| `test_data_generation(self, C = 10, gamma = 4, Nlc = 36, Nseq = 25, fs = 0.3, extend = False, mat_ref = None, sdata = None, fontsize = 16, gridsearch = False, cvals = None, gvals = None, Fe = 0.1, Ce = 0.99, reversal = False)` | 1838 | A function to generate test data to get the scores, which is exactly as we are generating |
| `create_sig_data(self, N = None, mat_ref = None, sdata = None, Nseq = 2, sflow = None, offs = 0.01, extend = False, rand = False, Fe = 0.1, Ce = 0.99)` | 1965 | Function to create consistent data sets on the deviatoric stress plane |
| `setup_fgrad_SVM(self)` | 2073 | Inititalize and train SVM regression on plastic strain increments in data |
| `export_MLparam(self, sname, source = None, file = None, path = '../../models/', descr = None, param = None)` | 2148 | The parameters of the trained Ml flow rule (support vectors, dual |
| `pckl(self, name = None, path = '../../materials/')` | 2289 | Write material into pickle file. Usefull for materials with trained machine |
| `create_scaled_input(self, sig, epl = None, acc_strain = None, max_stress = None, flag = None, tex = None)` | 2315 | Transforms np.array x to be used by SVM. |
| `GridSearchCVTexture(self, x, param_grid, n_splits, verbose = True)` | 2384 | Function to perform Grid Search Cross Validation over the textures. The difference compared to standard grid |
| `elasticity(self, C11 = None, C12 = None, C44 = None, CV = None, E = None, nu = None)` | 2415 | Define elastic material properties |
| `plasticity(self, sy = None, sdim = 6, drucker = 0.0, khard = 0.0, tresca = False, barlat = None, barlat_exp = None, hill = None, hill_3p = None, hill_6p = None, rv = None, lhs = None)` | 2480 | Define plastic material parameters; anisotropic Hill-like and Drucker-like |
| `from_data(self, param)` | 2612 | Define material properties from data sets generated in module `Data`: |
| `from_MLparam(self, name, path = '../../models/')` | 2704 | Define material properties from parameters of trained machine learning |
| `set_texture(self, current, verb = False)` | 2721 | Set parameters for current crystallographic texture of material as defined in microstructure. |
| `ellipsis(self, a = 1.0, b = 1.0 / np.sqrt(3.0), n = 72)` | 2788 | Create ellipsis with main axis along 45° axis, used for graphical representation of isotropic yield locus. |
| `plot_data(self, Z, axs, xx, yy, field = True, c = 'red')` | 2810 | Plotting data in stress space to visualize yield loci. |
| `plot_yield_locus(self, fun = None, label = None, data = None, trange = 0.01, peeq = 0.0, xstart = None, xend = None, axis1 = [0], axis2 = [1], iso = False, ref_mat = None, field = False, Nmesh = 100, file = None, fontsize = 20, scaling = True)` | 2851 | Plot different cuts through yield locus in 3D principal stress space. |
| `calc_properties(self, size = 2, Nel = 2, verb = False, eps = 0.005, min_step = None, sigeps = False, load_cases = ['stx', 'sty', 'et2', 'ect'])` | 3078 | Use pylabfea.model to calculate material strength and stress-strain |
| `plot_stress_strain(self, Hill = False, file = None, fontsize = 14)` | 3184 | Plot stress-strain data and print values for strength. Requires |
| `polar_plot_yl(self, Na = 72, cmat = None, data = None, dname = 'reference', scaling = None, field = False, predict = False, cbar = False, Np = 100, file = None, arrow = False, sJ2 = False, show = True)` | 3236 | Plot yield locus as polar plot in deviatoric stress plane |


## `pylabfea.model`

- 文件：`src/pylabfea/model.py`
- 模块说明：Module pylabefea.model introduces global functions for mechanical quantities

### 类与方法

#### `Model(object)`

- 行号：24
- 说明：Class for finite element model. Defines necessary attributes and methods

| 方法 | 行号 | 说明 |
|---|---:|---|
| `geom(self, sect = 1, LX = None, LY = 1.0, LZ = 1.0)` | 514 | Specify geometry of FE model with dimensions ``LX``, ``LY`` and ``LZ`` and |
| `assign(self, mats)` | 554 | Assigns an object of class ``Material`` to each section. |
| `bcleft(self, val = 0.0, bctype = 'disp', bcdir = 'x')` | 580 | Define boundary conditions on lhs nodes, either force or |
| `bcright(self, val, bctype, bcdir = 'x')` | 614 | Define boundary conditions on rhs nodes, either force or |
| `bcbot(self, val = 0.0, bctype = 'disp', bcdir = 'y')` | 646 | Define boundary conditions on bottom nodes, either force or |
| `bctop(self, val, bctype, bcdir = 'y')` | 682 | Define boundary conditions on top nodes, either force or displacement type. |
| `bcnode(self, node, val, bctype, bcdir)` | 715 | Define boundary conditions on a set of nodes defined in ``node``, |
| `mesh(self, elmts = None, nodes = None, NX = 10, NY = 1, SF = 1)` | 758 | Import mesh or |
| `setupK(self)` | 954 | Calculate and assemble system stiffness matrix based on element stiffness matrices. |
| `solve(self, min_step = None, verb = False)` | 979 | Solve linear system of equations K.u = f with respect to u, to obtain distortions |
| `bcval(self, nodes)` | 1452 | Calculate average displacement and total force at (boundary) nodes |
| `calc_global(self)` | 1473 | Calculate global quantities and store in Model.glob; |
| `plot(self, fsel, mag = 10, colormap = 'viridis', cdepth = 20, showmesh = True, shownodes = True, vmin = None, vmax = None, annot = True, file = None, showfig = True, pos_bar = 0.83, fig = None, ax = None, showbar = True)` | 1513 | Produce graphical output: draw elements in deformed shape with color |


## `pylabfea.training`

- 文件：`src/pylabfea/training.py`
- 模块说明：Module pylabfea.training introduces methods to create training data for ML flow rule

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `int_sin_m(x, m)` | 33 | Computes the integral of sin^m(t) dt from 0 to x recursively |
| `primes()` | 57 | Infinite generator of prime numbers |
| `uniform_hypersphere(d, n, method = 'brentq')` | 83 | Generate n usnits stresse on the d dimensional hypersphere |
| `load_cases(number_3d, number_6d, method = 'brentq')` | 124 | Generate unit stresses in principal stress space (3d) and full stress space (6d) |
| `training_score(yf_ref, yf_ml, plot = False)` | 151 | Calculate the accuracy of the training result in form of different measures |
| `create_test_sig(file, number_sig_per_strain = 4)` | 244 | A function to generate test data for micromechanical simulations based on a given material's stress-strain data. |

## `material_ai_workbench.__init__`

- 文件：`material_ai_workbench/__init__.py`
- 模块说明：MaterialAI Workbench built on top of the bundled pyLabFEA fork.

## `material_ai_workbench.abaqus_batch_client`

- 文件：`material_ai_workbench/abaqus_batch_client.py`
- 模块说明：Batch Abaqus Python helpers for ODB post-processing.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `extract_odb_field_summary_batch(odb_path: Path \| str, *, fields: list[str] \| tuple[str, ...] \| None = None, max_values_per_field: int = 500000, max_history_outputs: int = 200, output_dir: Path \| str \| None = None, config: AbaqusBatchConfig \| None = None)` | 25 | Extract final-frame ODB field statistics with Abaqus SMAPython. |
| `extract_odb_frame_series_batch(odb_path: Path \| str, *, fields: list[str] \| tuple[str, ...] \| None = None, region_names: list[str] \| tuple[str, ...] \| None = None, max_values_per_field: int = 200000, max_frames_per_step: int = 500, output_dir: Path \| str \| None = None, config: AbaqusBatchConfig \| None = None)` | 88 | Extract per-frame aggregate curves from an ODB with Abaqus SMAPython. |

### 类与方法

#### `AbaqusBatchError(RuntimeError)`

- 行号：15
- 说明：Raised when an Abaqus batch post-processing command fails.

#### `AbaqusBatchConfig`

- 行号：20


## `material_ai_workbench.abaqus_bridge`

- 文件：`material_ai_workbench/abaqus_bridge.py`
- 模块说明：Prepare and optionally run Abaqus UMAT verification for a Workbench run.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `prepare_abaqus_verification(config: AbaqusBridgeConfig)` | 57 | 待补充 |
| `run_abaqus_verification(config: AbaqusBridgeConfig)` | 107 | 待补充 |
| `main()` | 183 | 待补充 |

### 类与方法

#### `AbaqusBridgeConfig`

- 行号：33

#### `AbaqusBridgeResult`

- 行号：44


## `material_ai_workbench.abaqus_diagnostics`

- 文件：`material_ai_workbench/abaqus_diagnostics.py`
- 模块说明：Abaqus installation, batch runtime and MCP bridge diagnostics.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `run_abaqus_diagnostics(config: AbaqusDiagnosticConfig \| None = None)` | 88 | Run read-only diagnostics and persist JSON plus Markdown evidence. |
| `main(argv: list[str] \| None = None)` | 414 | 待补充 |

### 类与方法

#### `DiagnosticCheck`

- 行号：35

#### `AbaqusDiagnosticConfig`

- 行号：48

#### `AbaqusDiagnosticReport`

- 行号：60

| 方法 | 行号 | 说明 |
|---|---:|---|
| `to_dict(self)` | 71 | 待补充 |


## `material_ai_workbench.abaqus_mcp_client`

- 文件：`material_ai_workbench/abaqus_mcp_client.py`
- 模块说明：Direct client for the Abaqus MCP socket bridge.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `request_bridge(method: str, params: dict[str, Any] \| None = None, config: AbaqusMcpConfig \| None = None)` | 65 | Send one request to the Abaqus GUI socket bridge. |
| `ping_bridge(config: AbaqusMcpConfig \| None = None)` | 108 | Return a user-facing connection status. |
| `execute_kernel_code(code: str, config: AbaqusMcpConfig \| None = None)` | 153 | Execute a small Python chunk inside the live Abaqus/CAE kernel. |
| `stop_bridge(config: AbaqusMcpConfig \| None = None)` | 166 | Request the Abaqus MCP socket bridge to stop. |
| `set_workdir(path: Path \| str, config: AbaqusMcpConfig \| None = None)` | 176 | 待补充 |
| `get_model_info(config: AbaqusMcpConfig \| None = None)` | 192 | 待补充 |
| `list_jobs(config: AbaqusMcpConfig \| None = None)` | 254 | 待补充 |
| `monitor_job_status(job_name: str = '', config: AbaqusMcpConfig \| None = None)` | 274 | 待补充 |
| `submit_job(job_name: str, config: AbaqusMcpConfig \| None = None)` | 332 | 待补充 |
| `inspect_odb(odb_path: Path \| str, config: AbaqusMcpConfig \| None = None)` | 348 | 待补充 |
| `extract_odb_field_summary(odb_path: Path \| str, *, fields: list[str] \| tuple[str, ...] \| None = None, max_values_per_field: int = 500000, max_history_outputs: int = 200, config: AbaqusMcpConfig \| None = None)` | 415 | Extract final-frame field statistics from an ODB through Abaqus/CAE. |
| `display_odb_contour(odb_path: Path \| str, *, field_label: str = 'S', invariant: str = 'Mises', output_position: str = 'INTEGRATION_POINT', config: AbaqusMcpConfig \| None = None)` | 688 | Display an ODB contour in the current Abaqus viewport before capture. |
| `capture_viewport(output_dir: Path \| str, viewport_name: str = '', image_format: str = 'PNG', config: AbaqusMcpConfig \| None = None)` | 771 | 待补充 |
| `create_session_snapshot(selected_run: Path \| None = None, config: AbaqusMcpConfig \| None = None, capture_image: bool = True, output_root: Path \| str \| None = None)` | 831 | Capture status/model/job/viewport information into a local report folder. |

### 类与方法

#### `AbaqusMcpError(RuntimeError)`

- 行号：31
- 说明：Raised when the Abaqus MCP bridge cannot complete a request.

#### `AbaqusMcpConnectionError(AbaqusMcpError)`

- 行号：35
- 说明：Raised when the Abaqus MCP bridge endpoint is unreachable.

#### `AbaqusMcpConfig`

- 行号：40

#### `AbaqusMcpStatus`

- 行号：47

#### `AbaqusMcpSnapshot`

- 行号：57


## `material_ai_workbench.batch_simulation`

- 文件：`material_ai_workbench/batch_simulation.py`
- 模块说明：Batch simulation planning and execution for MaterialAI Workbench.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `create_parameter_sweep_plan(*, name: str = 'batch_j2_sweep', material_type: str = 'j2', yield_strengths: list[float] \| tuple[float, ...] = DEFAULT_YIELD_STRENGTHS, youngs_modulus: float = 200000.0, poisson_ratio: float = 0.3, hill_ratios: tuple[float, float, float, float, float, float] = DEFAULT_HILL_RATIOS, c_value: float = 1.0, gamma: float = 1.0, n_load_cases: int = 32, n_sequence: int = 3, test_size: int = 60, plot_mesh: int = 40, max_abaqus_load_cases: int = 1, output_root: Path = BATCH_ROOT)` | 73 | Create a small batch plan for material-parameter sample expansion. |
| `load_batch_plan(plan_dir: Path \| str)` | 144 | Load a batch plan folder or batch_plan.json file. |
| `save_batch_plan(plan: BatchPlan)` | 153 | 待补充 |
| `list_batch_plans(root: Path = BATCH_ROOT)` | 165 | Return batch plan folders, newest first. |
| `run_batch_plan(plan_dir: Path \| str, *, run_abaqus: bool = False, archive_cases: bool = False, postprocess_odb: bool = False, export_dataset_after: bool = False, train_surrogate_after: bool = False, max_samples: int \| None = None, timeout_seconds: int = 1800)` | 178 | Run pending/failed samples in a batch plan. |
| `batch_sample_table_rows(plan: BatchPlan \| dict[str, Any])` | 250 | Return compact rows for Streamlit and reports. |
| `summarize_batch_with_llm(batch_dir: Path \| str)` | 559 | Generate an optional LLM summary for a batch plan. |

### 类与方法

#### `BatchPlan`

- 行号：60

| 方法 | 行号 | 说明 |
|---|---:|---|
| `samples(self)` | 68 | 待补充 |


## `material_ai_workbench.case_based_workflow`

- 文件：`material_ai_workbench/case_based_workflow.py`
- 模块说明：Prepare a traceable Abaqus run workspace from grounded historical cases.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `prepare_case_based_plan(payload: dict[str, Any], *, cases_root: Path = CASES_ROOT, output_root: Path = CASE_PLAN_ROOT)` | 44 | Clone editable inputs and write a reviewable, non-submitted job plan. |

### 类与方法

#### `CaseBasedPlanResult`

- 行号：35


## `material_ai_workbench.case_cli`

- 文件：`material_ai_workbench/case_cli.py`
- 模块说明：Command-line interface for Abaqus case ingestion and dataset governance.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `build_parser()` | 22 | 待补充 |
| `main(argv: Sequence[str] \| None = None)` | 78 | 待补充 |

## `material_ai_workbench.case_intelligence`

- 文件：`material_ai_workbench/case_intelligence.py`
- 模块说明：Explainable retrieval and LLM grounding for local simulation cases.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `rank_similar_cases(query_case: Any, candidates: Iterable[Any], *, top_k: int = 5, weights: dict[str, float] \| None = None)` | 50 | Rank cases with transparent material, geometry, load and mesh evidence. |
| `search_cases_by_text(query: str, *, cases: Iterable[Any] \| None = None, cases_root: Any = None, top_k: int = 5, training_eligible_only: bool = False)` | 128 | Retrieve local cases for a free-text engineering request. |
| `build_case_grounding_context(prompt: str, *, cases: Iterable[Any] \| None = None, cases_root: Any = None, top_k: int = 3)` | 179 | Build a compact, path-free context block for an external LLM planner. |
| `grounding_provenance(context: dict[str, Any])` | 236 | Return the immutable provenance subset attached to an LLM plan. |

## `material_ai_workbench.case_library`

- 文件：`material_ai_workbench/case_library.py`
- 模块说明：Abaqus case-library utilities for MaterialAI Workbench.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `scan_case_folder(source_folder: Path \| str, *, title: str, tags: list[str] \| str \| None = None, description: str = '', status: str = 'success', parameters: dict[str, Any] \| None = None, lessons_learned: str = '', next_actions: str = '', units: dict[str, Any] \| str \| None = None, solver_version: str = '', source_mode: str = 'reference', cases_root: Path = CASES_ROOT)` | 138 | 待补充 |
| `batch_import_cases(parent_folder: Path \| str, *, tags: list[str] \| None = None, status: str = 'success', cases_root: Path = CASES_ROOT, skip_existing: bool = True, units: dict[str, Any] \| str \| None = None, solver_version: str = '', source_mode: str = 'reference')` | 224 | Scan a parent folder and import all sub-folders as individual cases. |
| `find_duplicate_cases(source_folder: Path \| str, *, cases_root: Path = CASES_ROOT)` | 289 | Check if a source folder has already been imported. |
| `save_case_summary(summary: CaseSummary)` | 353 | 待补充 |
| `write_case_report(summary: CaseSummary)` | 371 | 待补充 |
| `list_cases(cases_root: Path = CASES_ROOT)` | 379 | 待补充 |
| `filter_cases(cases: list[CaseSummary], *, tags: list[str] \| str \| None = None, statuses: list[str] \| tuple[str, ...] \| None = None, material_types: list[str] \| tuple[str, ...] \| None = None, case_types: list[str] \| tuple[str, ...] \| None = None, date_from: str \| None = None, date_to: str \| None = None)` | 391 | 待补充 |
| `infer_case_type(case: CaseSummary)` | 440 | 待补充 |
| `find_similar_cases(query: CaseSummary \| Path \| str, *, cases: list[CaseSummary] \| None = None, cases_root: Path = CASES_ROOT, top_k: int = 5, weights: dict[str, float] \| None = None)` | 461 | Rank archived cases with explainable hybrid engineering similarity. |
| `load_case_summary(case_dir: Path \| str)` | 487 | 待补充 |
| `case_table_rows(cases: list[CaseSummary])` | 510 | 待补充 |
| `file_table_rows(summary: CaseSummary, category: str \| None = None)` | 534 | 待补充 |
| `inp_feature_table_rows(summary: CaseSummary)` | 555 | 待补充 |
| `result_feature_table_rows(summary: CaseSummary)` | 574 | 待补充 |
| `odb_extraction_table_rows(summary: CaseSummary)` | 623 | 待补充 |
| `odb_frame_series_table_rows(summary: CaseSummary)` | 642 | 待补充 |
| `append_odb_extraction(summary: CaseSummary, extraction: dict[str, Any])` | 660 | 待补充 |
| `append_odb_frame_series(summary: CaseSummary, series: dict[str, Any])` | 675 | 待补充 |
| `extract_inp_features(inp_path: Path \| str)` | 684 | 待补充 |
| `extract_csv_result_features(csv_path: Path \| str)` | 693 | 待补充 |

### 类与方法

#### `CaseFile`

- 行号：88

#### `CaseSummary`

- 行号：101


## `material_ai_workbench.case_package`

- 文件：`material_ai_workbench/case_package.py`
- 模块说明：Stable case-package contract and quality gates for archived Abaqus work.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `normalize_case_units(units: dict[str, Any] \| str \| None, parameters: dict[str, Any] \| None = None)` | 37 | Normalize an explicit Abaqus unit declaration without guessing units. |
| `fingerprint_file(path: Path \| str, size_bytes: int \| None = None)` | 78 | Return a full hash for normal files and a bounded sampled hash for large files. |
| `fingerprint_case_files(files: Iterable[Any])` | 104 | Build a stable source fingerprint from ordered relative paths and file hashes. |
| `evaluate_case_quality(summary: Any)` | 124 | Evaluate whether an indexed case is trustworthy enough for ML training. |
| `build_case_package(summary: Any)` | 324 | Build the public, versioned case-package document from an internal summary. |
| `write_case_package(summary: Any)` | 387 | 待补充 |
| `load_case_package(case_dir: Path \| str)` | 396 | 待补充 |
| `quality_table_rows(quality: dict[str, Any])` | 409 | 待补充 |

## `material_ai_workbench.closed_loop_report`

- 文件：`material_ai_workbench/closed_loop_report.py`
- 模块说明：Closed-loop validation report utilities for MaterialAI Workbench.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `generate_closed_loop_report(*, material_run: Path \| str \| None = None, case_dir: Path \| str \| None = None, dataset_dir: Path \| str \| None = None, surrogate_run: Path \| str \| None = None, batch_plan: Path \| str \| None = None, output_root: Path = CLOSED_LOOP_ROOT)` | 32 | Generate a Markdown report that links the MVP CAE + AI loop together. |
| `list_closed_loop_reports(root: Path = CLOSED_LOOP_ROOT)` | 102 | Return generated closed-loop report folders, newest first. |

### 类与方法

#### `ClosedLoopReport`

- 行号：25


## `material_ai_workbench.composite_benchmarks`

- 文件：`material_ai_workbench/composite_benchmarks.py`
- 模块说明：Traceable literature and experimental benchmarks for composite ML work.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `load_composite_benchmark_registry(path: Path \| str \| None = None)` | 31 | Load and validate the packaged registry or a user-supplied registry file. |
| `load_composite_benchmarks(path: Path \| str \| None = None)` | 54 | Return validated benchmark entries. |
| `composite_benchmark_rows(path: Path \| str \| None = None, *, task_kind: str \| None = None, reproduction_status: str \| None = None)` | 60 | Return flattened rows suitable for the desktop or Streamlit tables. |
| `validate_composite_benchmark_registry(payload: Any, *, source_name: str = 'composite benchmark registry')` | 103 | Validate provenance fields and prevent unearned reproduction claims. |

## `material_ai_workbench.composite_dataset`

- 文件：`material_ai_workbench/composite_dataset.py`
- 模块说明：Composite RVE dataset and surrogate utilities.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `create_composite_batch_plan(config: CompositeBatchConfig)` | 100 | 待补充 |
| `list_composite_batch_plans(root: Path = COMPOSITE_BATCH_ROOT)` | 126 | 待补充 |
| `load_composite_batch_plan(plan_dir: Path \| str)` | 136 | 待补充 |
| `run_composite_batch_plan(plan_dir: Path \| str, *, max_samples: int \| None = None)` | 151 | 待补充 |
| `build_composite_dataset(plan_dir: Path \| str, output_csv: Path \| str \| None = None)` | 183 | 待补充 |
| `train_composite_surrogate(dataset_csv: Path \| str, *, target_column: str = DEFAULT_COMPOSITE_TARGET, model_kind: str = 'random_forest', output_root: Path = COMPOSITE_SURROGATE_ROOT, random_state: int = 42, uncertainty: str = 'none')` | 204 | 待补充 |
| `list_composite_surrogate_runs(root: Path = COMPOSITE_SURROGATE_ROOT)` | 268 | 待补充 |
| `composite_surrogate_comparison_rows(runs: list[Path \| str] \| None = None, *, dataset_csv: Path \| str \| None = None, target_column: str \| None = None)` | 275 | 待补充 |

### 类与方法

#### `CompositeBatchConfig`

- 行号：50

#### `CompositeBatchPlan`

- 行号：80

#### `CompositeSurrogateRun`

- 行号：90


## `material_ai_workbench.composite_workflow`

- 文件：`material_ai_workbench/composite_workflow.py`
- 模块说明：Composite micro-to-macro workflow for a 3D Abaqus plate-with-hole case.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `run_composite_plate_workflow(config: CompositePlateConfig)` | 93 | 待补充 |
| `compute_effective_ud_properties(config: CompositePlateConfig)` | 232 | 待补充 |
| `build_pylabfea_material_summary(config: CompositePlateConfig, props: dict[str, float])` | 270 | 待补充 |
| `estimate_plate_response(config: CompositePlateConfig, props: dict[str, float])` | 312 | 待补充 |
| `list_composite_runs(root: Path = COMPOSITE_ROOT)` | 338 | 待补充 |
| `load_composite_manifest(run_dir: Path \| str)` | 348 | 待补充 |
| `distance_point_to_segment(point_xyz: tuple[float, float, float], start_xyz: tuple[float, float, float] \| list[float], end_xyz: tuple[float, float, float] \| list[float])` | 384 | Return the Euclidean distance from a point to a finite 3D segment. |
| `classify_voxel_phase(point_xyz: tuple[float, float, float], fibers: list[dict[str, Any]], fiber_radius: float, interface_radius: float)` | 396 | Classify a voxel center using the same oriented fiber geometry as the UI. |
| `generate_fiber_layout(config: CompositePlateConfig)` | 424 | Generate 3D oriented fiber segments with angles, orientation tensor, and Vf calibration. |
| `write_microstructure_preview(path: Path, config: CompositePlateConfig, layout: dict[str, Any])` | 665 | 待补充 |
| `write_micro_rve_inp(path: Path, phase_map_path: Path, config: CompositePlateConfig, layout: dict[str, Any])` | 746 | 待补充 |
| `micro_rve_load_cases(config: CompositePlateConfig)` | 936 | 待补充 |
| `write_micro_rve_pbc_jobs(job_dir: Path, config: CompositePlateConfig, layout: dict[str, Any])` | 948 | 待补充 |
| `write_micro_pbc_plan(path: Path, config: CompositePlateConfig, jobs: dict[str, Path])` | 1153 | 待补充 |
| `write_micro_pbc_run_script(path: Path, config: CompositePlateConfig, job_dir: Path, jobs: dict[str, Path])` | 1171 | 待补充 |
| `write_micro_pbc_postprocess_script(path: Path, config: CompositePlateConfig, job_dir: Path)` | 1182 | 待补充 |
| `run_micro_rve_pbc_homogenization(config: CompositePlateConfig, job_dir: Path, postprocess_script: Path, run_dir: Path)` | 1310 | 待补充 |
| `write_micro_rve_run_script(path: Path, config: CompositePlateConfig, micro_inp: Path, run_dir: Path)` | 1446 | 待补充 |
| `write_plate_preview(path: Path, config: CompositePlateConfig, estimates: dict[str, float])` | 1455 | 待补充 |
| `write_material_card(path: Path, props: dict[str, float])` | 1508 | 待补充 |
| `write_abaqus_build_script(path: Path, config: CompositePlateConfig, props: dict[str, float], run_dir: Path)` | 1521 | 待补充 |
| `write_odb_postprocess_script(path: Path, config: CompositePlateConfig, run_dir: Path)` | 1646 | 待补充 |
| `write_run_script(path: Path, config: CompositePlateConfig, abaqus_script: Path, post_script: Path, run_dir: Path)` | 1703 | 待补充 |
| `write_dataset_row(path: Path, config: CompositePlateConfig, props: dict[str, float], estimates: dict[str, float], micro_metrics: dict[str, float], *, estimated_props: dict[str, float] \| None = None, pbc_summary: dict[str, Any] \| None = None)` | 1720 | 待补充 |
| `run_abaqus_build(config: CompositePlateConfig, abaqus_script: Path, postprocess_script: Path, run_dir: Path)` | 1791 | 待补充 |

### 类与方法

#### `CompositePlateConfig`

- 行号：23

#### `CompositePlateResult`

- 行号：67


## `material_ai_workbench.config`

- 文件：`material_ai_workbench/config.py`
- 模块说明：Central configuration for MaterialAI Workbench.

## `material_ai_workbench.data_import`

- 文件：`material_ai_workbench/data_import.py`
- 模块说明：CSV import utilities for material curves and Abaqus batch results.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `import_csv_dataset(*, source_path: Path \| None = None, source_bytes: bytes \| None = None, source_name: str = 'uploaded.csv', source_kind: str = 'experiment_curve', material_name: str = 'imported_material', imports_root: Path = IMPORTS_ROOT)` | 62 | 待补充 |
| `validate_imported_curve_with_workbench(import_dir: Path \| str, *, material_type: str = 'j2', output_dir: Path \| None = None, poisson_ratio: float = 0.3, n_load_cases: int = 24, test_size: int = 40)` | 149 | Train a workbench material from an imported curve and compare curves. |
| `list_imports(imports_root: Path = IMPORTS_ROOT)` | 227 | 待补充 |
| `load_import_summary(import_dir: Path)` | 237 | 待补充 |
| `workbench_config_from_import(import_dir: Path \| str, *, material_type: str = 'j2', output_dir: Path \| None = None, name: str \| None = None)` | 241 | Create a starter WorkbenchConfig from a normalized experimental curve. |
| `imported_curve_to_config(import_dir: Path \| str, *, material_type: str = 'j2', output_dir: Path \| None = None, poisson_ratio: float = 0.3)` | 266 | Build a WorkbenchConfig from an imported experimental stress-strain curve. |
| `read_normalized_preview(path: Path, limit: int = 30)` | 330 | 待补充 |

### 类与方法

#### `DataImportResult`

- 行号：30

#### `DataImportValidationResult`

- 行号：49


## `material_ai_workbench.dataset_export`

- 文件：`material_ai_workbench/dataset_export.py`
- 模块说明：Dataset export utilities for the MaterialAI Workbench case library.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `export_case_dataset(*, cases_root: Path = CASES_ROOT, output_root: Path = DATASETS_ROOT, name: str = 'case_dataset', case_dirs: list[Path \| str] \| tuple[Path \| str, ...] \| None = None, training_only: bool = False)` | 37 | Export case-library features into CSV assets for ML experiments. |
| `create_dataset_split(dataset_csv: Path \| str, *, output_dir: Path \| None = None, test_fraction: float = 0.25, random_seed: int = 42)` | 460 | Create train/validation split manifest for a case dataset. |

### 类与方法

#### `DatasetExport`

- 行号：24


## `material_ai_workbench.desktop_launcher`

- 文件：`material_ai_workbench/desktop_launcher.py`
- 模块说明：Windows desktop launcher for MaterialAI Workbench.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `default_app_root()` | 56 | Return the per-user application-data directory. |
| `configure_desktop_environment(app_root: Path \| None = None)` | 63 | Create writable folders and expose them to the workbench backend. |
| `configure_logging(paths: DesktopPaths, *, debug: bool = False)` | 89 | Configure a rotating log that remains available after GUI failures. |
| `find_available_port(requested_port: int \| None = None)` | 105 | Reserve-check a loopback port and return it for the backend process. |
| `streamlit_app_path()` | 121 | Locate the Streamlit entry file in source and frozen builds. |
| `backend_command(port: int, *, debug: bool = False)` | 129 | Build the child command for source and PyInstaller execution. |
| `run_streamlit_server(port: int, *, debug: bool = False)` | 139 | Run the private Streamlit backend in the current process. |
| `start_backend(port: int, paths: DesktopPaths, *, debug: bool = False)` | 166 | Start the backend without displaying a second console window. |
| `wait_for_backend(process: subprocess.Popen[bytes], port: int, *, timeout_seconds: float = DEFAULT_STARTUP_TIMEOUT)` | 195 | Wait until Streamlit reports healthy or fail with actionable context. |
| `stop_backend(process: subprocess.Popen[bytes] \| None)` | 225 | Stop the owned backend and prevent orphaned localhost servers. |
| `log_tail(path: Path, *, max_lines: int = 24)` | 239 | Return the end of a UTF-8 log without failing the error dialog. |
| `run_core_self_check(paths: DesktopPaths)` | 248 | Exercise the packaged numerical stack with a small material-training run. |
| `verify_native_window_runtime()` | 281 | Load the Windows pywebview backend and its bundled WebView2 assemblies. |
| `open_native_window(url: str, *, debug: bool = False)` | 321 | Open the workbench URL in a native Windows webview window. |
| `run_browser_mode(url: str, process: subprocess.Popen[bytes])` | 341 | Open the app in the default browser for development diagnostics. |
| `show_message(title: str, message: str, *, error: bool = False)` | 353 | Show a native message box when no console is available. |
| `build_parser()` | 363 | 待补充 |
| `main(argv: Sequence[str] \| None = None)` | 395 | 待补充 |

### 类与方法

#### `DesktopLaunchError(RuntimeError)`

- 行号：35
- 说明：Raised when the desktop client cannot start safely.

#### `DesktopAlreadyRunning(DesktopLaunchError)`

- 行号：39
- 说明：Raised when another desktop client instance already owns the mutex.

#### `DesktopPaths`

- 行号：44
- 说明：Writable per-user paths used by the packaged desktop client.

#### `SingleInstanceGuard`

- 行号：295
- 说明：Windows named-mutex guard; a no-op on other platforms.


## `material_ai_workbench.engineering_report`

- 文件：`material_ai_workbench/engineering_report.py`
- 模块说明：Chinese engineering report generator for MaterialAI Workbench.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `generate_engineering_report(run_dir: Path \| str, *, output_path: Path \| str \| None = None, report_type: str = 'metal_closed_loop')` | 16 | Generate a Chinese engineering report from a completed run. |

## `material_ai_workbench.experimental_datasets`

- 文件：`material_ai_workbench/experimental_datasets.py`
- 模块说明：Governed ingestion for public experimental composite datasets.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `prepare_cfrp_experimental_dataset(*, source_path: Path \| str \| None = None, output_root: Path \| str = DATASETS_ROOT, accept_license: bool = False, timeout_seconds: float = 60.0, spec: ExperimentalDatasetSpec = ALSHEGHRI_CFRP_SPEC)` | 214 | Verify, normalize, audit, and split the public CFRP workbook. |
| `fetch_mendeley_file_metadata(spec: ExperimentalDatasetSpec = ALSHEGHRI_CFRP_SPEC, *, timeout_seconds: float = 30.0)` | 341 | Read and validate the current official file metadata. |
| `validate_mendeley_file_metadata(payload: Any, *, spec: ExperimentalDatasetSpec = ALSHEGHRI_CFRP_SPEC)` | 360 | Validate Mendeley file-list JSON without downloading the workbook. |
| `read_cfrp_experimental_workbook(path: Path \| str)` | 428 | Parse the known source workbook into a stable, unit-labelled schema. |
| `build_cfrp_quality_report(rows: list[dict[str, Any]], *, spec: ExperimentalDatasetSpec = ALSHEGHRI_CFRP_SPEC)` | 529 | Build an auditable profile without dropping or imputing source rows. |
| `build_grouped_split_manifest(rows: list[dict[str, Any]], *, spec: ExperimentalDatasetSpec = ALSHEGHRI_CFRP_SPEC)` | 602 | Create target-specific leave-one-material-type-out evaluation folds. |

### 类与方法

#### `ExperimentalDatasetSpec`

- 行号：30

#### `ExperimentalDatasetResult`

- 行号：202


## `material_ai_workbench.job_queue`

- 文件：`material_ai_workbench/job_queue.py`
- 模块说明：Persistent serial Abaqus job queue.

### 类与方法

#### `QueuedJob`

- 行号：23

#### `JobQueue`

- 行号：39
- 说明：Small disk-backed FIFO queue for local Abaqus jobs.

| 方法 | 行号 | 说明 |
|---|---:|---|
| `submit(self, name: str, input_file: str \| Path, work_dir: str \| Path, cpus: int = 4, *, retry_of: str \| None = None)` | 55 | 待补充 |
| `process_next(self, timeout_seconds: int = 7200)` | 79 | 待补充 |
| `status(self)` | 130 | 待补充 |
| `list_jobs(self)` | 136 | 待补充 |
| `clear_completed(self)` | 139 | 待补充 |
| `retry(self, job_id: str)` | 143 | 待补充 |
| `history(self)` | 155 | 待补充 |
| `statistics(self)` | 165 | 待补充 |
| `log_text(self, job_id: str, *, max_chars: int = 8000)` | 181 | 待补充 |


## `material_ai_workbench.llm_adapter`

- 文件：`material_ai_workbench/llm_adapter.py`
- 模块说明：Optional LLM adapter for natural-language simulation planning.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `read_env_file(path: Path = ENV_FILE)` | 77 | 待补充 |
| `write_env_values(path: Path, updates: dict[str, str])` | 93 | 待补充 |
| `provider_preset(provider_key: str)` | 206 | 待补充 |
| `llm_config_from_env(env_path: Path = ENV_FILE)` | 210 | 待补充 |
| `apply_llm_config(config: LlmChatConfig, api_key_value: str \| None = None)` | 241 | 待补充 |
| `save_llm_config(config: LlmChatConfig, api_key_value: str \| None = None, env_path: Path = ENV_FILE)` | 253 | 待补充 |
| `test_llm_connection(config: LlmChatConfig, *, api_key_value: str \| None = None, transport: Transport \| None = None)` | 270 | 待补充 |
| `plan_task_with_llm(prompt: str, config: LlmChatConfig, transport: Transport \| None = None, case_context: dict[str, Any] \| None = None)` | 296 | Call an OpenAI-compatible chat endpoint and parse a task JSON response. |
| `interpret_report(report_text: str, report_type: str = 'material_model', *, config: LlmChatConfig \| None = None, transport: Transport \| None = None)` | 384 | Generate an optional LLM interpretation for a Workbench report. |

### 类与方法

#### `LlmConfigError(RuntimeError)`

- 行号：135
- 说明：Raised when an LLM request is not configured enough to run.

#### `LlmResponseError(RuntimeError)`

- 行号：139
- 说明：Raised when the LLM response cannot be converted into a task JSON.

#### `LlmChatConfig`

- 行号：144

| 方法 | 行号 | 说明 |
|---|---:|---|
| `api_key(self)` | 165 | 待补充 |
| `validate(self)` | 168 | 待补充 |
| `to_public_dict(self)` | 182 | 待补充 |

#### `LlmTaskPlan`

- 行号：190

#### `LlmConnectionTest`

- 行号：198


## `material_ai_workbench.logging_config`

- 文件：`material_ai_workbench/logging_config.py`
- 模块说明：Logging helpers for MaterialAI Workbench.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `configure_logging(level: int = logging.INFO)` | 17 | Configure console and rotating-file logging once per process. |
| `get_logger(name: str)` | 42 | 待补充 |

## `material_ai_workbench.material_library`

- 文件：`material_ai_workbench/material_library.py`
- 模块说明：JSON-backed material preset library for MaterialAI Workbench.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `load_material_presets()` | 56 | 待补充 |
| `save_material_preset(preset: MaterialPreset)` | 66 | 待补充 |
| `delete_material_preset(name: str)` | 73 | 待补充 |
| `ensure_material_library()` | 79 | 待补充 |
| `preset_to_training_state(preset: MaterialPreset)` | 154 | 待补充 |
| `preset_to_workbench_config(preset: MaterialPreset, *, output_dir: Path \| None = None, name_suffix: str = '', calculate_curves: bool \| None = None)` | 178 | 待补充 |
| `preset_from_training_state(name: str, state: dict[str, Any], notes: str = '')` | 209 | 待补充 |

### 类与方法

#### `MaterialPreset`

- 行号：20

| 方法 | 行号 | 说明 |
|---|---:|---|
| `normalized(self)` | 43 | 待补充 |


## `material_ai_workbench.multi_fidelity`

- 文件：`material_ai_workbench/multi_fidelity.py`
- 模块说明：Multi-fidelity surrogate models for pyLabFEA and Abaqus data.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `train_multi_fidelity(X_low: np.ndarray, y_low: np.ndarray, X_high: np.ndarray, y_high: np.ndarray, *, name: str = 'multi_fidelity', output_root: Path = SURROGATES_ROOT, random_state: int = 42)` | 40 | Train an additive correction model: high ~= low_model + residual_model. |

### 类与方法

#### `MultiFidelityResult`

- 行号：29


## `material_ai_workbench.nl_tasks`

- 文件：`material_ai_workbench/nl_tasks.py`
- 模块说明：Rule-based natural-language task parser for MaterialAI Workbench v0.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `parse_natural_language_task(text: str)` | 69 | 待补充 |
| `task_from_dict(payload: dict[str, Any], source_text: str = '')` | 169 | Convert a structured task JSON into the internal task dataclasses. |
| `task_to_workbench_config(task: ParsedSimulationTask, output_dir: Path)` | 221 | 待补充 |

### 类与方法

#### `MaterialTaskSpec`

- 行号：19

#### `MLTaskSpec`

- 行号：31

#### `AbaqusTaskSpec`

- 行号：43

#### `ParsedSimulationTask`

- 行号：50

| 方法 | 行号 | 说明 |
|---|---:|---|
| `to_dict(self)` | 59 | 待补充 |
| `to_json(self)` | 65 | 待补充 |


## `material_ai_workbench.odb_postprocess`

- 文件：`material_ai_workbench/odb_postprocess.py`
- 模块说明：ODB post-processing helpers for MaterialAI Workbench case library.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `run_case_odb_extraction(summary: CaseSummary, odb_path: Path \| str, *, fields: list[str] \| tuple[str, ...] \| None = None, max_values_per_field: int = 500000, capture_contour: bool = True, backend: str = 'auto', config: AbaqusMcpConfig \| None = None, batch_config: AbaqusBatchConfig \| None = None)` | 29 | Extract ODB field summaries and persist them under a case directory. |
| `extraction_summary_rows(extraction: dict[str, Any])` | 88 | 待补充 |
| `run_case_odb_frame_series_extraction(summary: CaseSummary, odb_path: Path \| str, *, fields: list[str] \| tuple[str, ...] \| None = None, region_names: list[str] \| tuple[str, ...] \| None = None, max_values_per_field: int = 200000, max_frames_per_step: int = 500, batch_config: AbaqusBatchConfig \| None = None)` | 108 | Extract per-frame field aggregate curves and persist them under a case. |
| `frame_series_rows(series: dict[str, Any])` | 149 | 待补充 |

## `material_ai_workbench.param_recommender`

- 文件：`material_ai_workbench/param_recommender.py`
- 模块说明：LLM-assisted parameter recommendation for MaterialAI Workbench.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `recommend_parameters(material_description: str, *, config: LlmChatConfig \| None = None)` | 25 | Recommend starter parameters from a natural-language material description. |

### 类与方法

#### `ParamRecommendation`

- 行号：17


## `material_ai_workbench.pipeline`

- 文件：`material_ai_workbench/pipeline.py`
- 模块说明：End-to-end material ML training workflow for the first Workbench prototype.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `run_material_workbench(config: WorkbenchConfig)` | 111 | 待补充 |

### 类与方法

#### `WorkbenchConfig`

- 行号：51

#### `WorkbenchResult`

- 行号：98


## `material_ai_workbench.plate_hole_acceptance`

- 文件：`material_ai_workbench/plate_hole_acceptance.py`
- 模块说明：Resumable Abaqus acceptance workflow for a 3D plate with a circular hole.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `run_plate_hole_acceptance(config: PlateHoleAcceptanceConfig \| None = None, *, execute: bool = False, run_dir: Path \| str \| None = None)` | 90 | Prepare or execute the plate-hole workflow and persist every state change. |
| `resume_plate_hole_acceptance(run_dir: Path \| str, *, execute: bool = True, submit_job: bool \| None = None, archive_case: bool \| None = None, backend: str \| None = None)` | 366 | Resume a prepared or interrupted run from its persisted configuration. |
| `main(argv: list[str] \| None = None)` | 1336 | 待补充 |

### 类与方法

#### `PlateHoleAcceptanceConfig`

- 行号：50

#### `PlateHoleAcceptanceResult`

- 行号：78


## `material_ai_workbench.plate_hole_batch`

- 文件：`material_ai_workbench/plate_hole_batch.py`
- 模块说明：Resumable 3D plate-hole Abaqus batch and surrogate-model pipeline.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `create_plate_hole_batch_plan(config: PlateHoleBatchConfig \| None = None)` | 77 | Create a Cartesian geometry/material/load plan without calling Abaqus. |
| `load_plate_hole_batch_plan(plan_dir: Path \| str)` | 147 | 待补充 |
| `list_plate_hole_batch_plans(root: Path = PLATE_HOLE_BATCH_ROOT)` | 160 | Return persisted plate-hole batch folders, newest first. |
| `save_plate_hole_batch_plan(plan: PlateHoleBatchPlan)` | 179 | 待补充 |
| `run_plate_hole_batch_plan(plan_dir: Path \| str, *, execute: bool = False, submit_jobs: bool = False, archive_cases: bool = True, export_dataset_after: bool = False, train_models_after: bool = False, max_samples: int \| None = None)` | 188 | Prepare or solve pending samples and optionally train RF/MLP/GBR surrogates. |
| `batch_table_rows(plan: PlateHoleBatchPlan \| dict[str, Any])` | 249 | 待补充 |
| `build_parser()` | 518 | 待补充 |
| `main(argv: Sequence[str] \| None = None)` | 544 | 待补充 |

### 类与方法

#### `PlateHoleBatchConfig`

- 行号：43

#### `PlateHoleBatchPlan`

- 行号：64

| 方法 | 行号 | 说明 |
|---|---:|---|
| `samples(self)` | 72 | 待补充 |


## `material_ai_workbench.run_composite_batch`

- 文件：`material_ai_workbench/run_composite_batch.py`
- 模块说明：Command-line tools for composite RVE batch data and surrogate training.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `main()` | 17 | 待补充 |

## `material_ai_workbench.run_composite_closed_loop`

- 文件：`material_ai_workbench/run_composite_closed_loop.py`
- 模块说明：Run one composite micro-to-Abaqus closed-loop acceptance case.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `main()` | 24 | 待补充 |

## `material_ai_workbench.run_composite_workflow`

- 文件：`material_ai_workbench/run_composite_workflow.py`
- 模块说明：Command-line entry point for the composite 3D plate-with-hole workflow.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `main()` | 12 | 待补充 |

## `material_ai_workbench.run_experimental_dataset`

- 文件：`material_ai_workbench/run_experimental_dataset.py`
- 模块说明：Prepare the traceable public CFRP experimental benchmark.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `build_parser()` | 18 | Build the command-line parser. |
| `main(argv: Sequence[str] \| None = None)` | 46 | Prepare the dataset and emit a machine-readable result. |

## `material_ai_workbench.run_metal_closed_loop`

- 文件：`material_ai_workbench/run_metal_closed_loop.py`
- 模块说明：CLI closed loop for metal plasticity batches.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `main()` | 25 | 待补充 |

## `material_ai_workbench.run_product_closed_loop`

- 文件：`material_ai_workbench/run_product_closed_loop.py`
- 模块说明：Product-level smoke closed loop for MaterialAI Workbench.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `run_product_closed_loop(config: CompositePlateConfig)` | 26 | 待补充 |
| `main()` | 80 | 待补充 |

## `material_ai_workbench.run_streamlit`

- 文件：`material_ai_workbench/run_streamlit.py`
- 模块说明：Console script entry point for launching the MaterialAI Workbench Streamlit app.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `main()` | 14 | Launch the Streamlit app from the installed package. |

## `material_ai_workbench.run_workbench`

- 文件：`material_ai_workbench/run_workbench.py`
- 模块说明：Command line entry point for the MaterialAI Workbench prototype.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `main()` | 11 | 待补充 |

## `material_ai_workbench.rve_visualization`

- 文件：`material_ai_workbench/rve_visualization.py`
- 模块说明：Interactive 3D fiber RVE visualization using plotly Mesh3d cylinders.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `cylinder_mesh_between_points(start: tuple[float, float, float], end: tuple[float, float, float], radius: float, n_sides: int = 16)` | 22 | Build a closed cylinder Mesh3d between two 3D points. |
| `plot_oriented_fiber_rve_3d(config: CompositePlateConfig \| None = None, *, layout: dict[str, Any] \| None = None, show_matrix: bool = True, show_interface: bool = True, width: int = 750, height: int = 650)` | 102 | Plot real fiber cylinders with interface layers using Mesh3d. |
| `build_rve_phase_grid(config: CompositePlateConfig)` | 226 | 待补充 |
| `plot_rve_3d(config = None, *, phase_grid = None, downsample = 1, opacity = 0.9, width = 750, height = 650)` | 250 | Legacy wrapper — delegates to the new fiber cylinder renderer. |
| `plot_rve_3d_from_run(run_dir: Path \| str, **kwargs)` | 258 | 待补充 |

## `material_ai_workbench.streamlit_app`

- 文件：`material_ai_workbench/streamlit_app.py`
- 模块说明：Streamlit front end for the MaterialAI Workbench prototype.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `main()` | 211 | 待补充 |

## `material_ai_workbench.surrogate_model`

- 文件：`material_ai_workbench/surrogate_model.py`
- 模块说明：Surrogate-model training utilities for case-library datasets.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `list_dataset_exports(root: Path = DATASETS_ROOT)` | 112 | Return dataset export folders that contain case_dataset.csv. |
| `list_surrogate_runs(root: Path = SURROGATES_ROOT)` | 128 | Return surrogate-model run folders, newest first. |
| `compare_all_models(dataset_dir: Path \| str, *, target_column: str = DEFAULT_TARGET, output_root: Path = SURROGATES_ROOT, random_state: int = 42)` | 141 | Train RF, MLP, and GBR on the same dataset and return a comparison table. |
| `surrogate_comparison_rows(runs: Iterable[Path \| str] \| None = None, *, dataset_dir: Path \| str \| None = None, target_column: str \| None = None)` | 206 | Build compact comparison rows from surrogate_metrics.json files. |
| `train_surrogate_from_dataset(dataset_dir: Path \| str, *, target_column: str = DEFAULT_TARGET, model_kind: str = 'random_forest', output_root: Path = SURROGATES_ROOT, random_state: int = 42, uncertainty: str = 'none')` | 271 | Train a small surrogate model from a case-dataset export. |

### 类与方法

#### `SurrogateRun`

- 行号：100


## `material_ai_workbench.task_schema`

- 文件：`material_ai_workbench/task_schema.py`
- 模块说明：Schema validation and dry-run preview for MaterialAI task plans.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `validate_task_payload(payload: dict[str, Any])` | 152 | Validate a task JSON payload against the schema for its task_type. |
| `infer_steps(payload: dict[str, Any])` | 239 | Return explicit or inferred execution steps for a task payload. |
| `build_executable_plan(payload: dict[str, Any])` | 272 | Merge defaults, validate schema, and build a UI-friendly execution plan. |
| `dry_run_summary(payload: dict[str, Any], schema_result: SchemaResult)` | 294 | Generate a human-readable dry-run summary of what would happen. |
| `merge_with_defaults(payload: dict[str, Any])` | 344 | Fill missing fields with sensible defaults so the plan can still execute. |

### 类与方法

#### `SchemaResult`

- 行号：123

#### `ExecutableStep`

- 行号：132

#### `ExecutablePlan`

- 行号：142

| 方法 | 行号 | 说明 |
|---|---:|---|
| `can_execute(self)` | 148 | 待补充 |


## `material_ai_workbench.time_series_surrogate`

- 文件：`material_ai_workbench/time_series_surrogate.py`
- 模块说明：Time-series surrogate for ODB frame curves.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `resample_curve(time_values: np.ndarray, field_values: np.ndarray, n_points: int = N_TIME_POINTS)` | 31 | Interpolate a curve to a normalized 0-1 grid. |
| `train_time_series_surrogate(frame_series_index_csv: str \| Path, case_dataset_csv: str \| Path, *, target_field: str = 'S', target_metric: str = 'max', n_time_points: int = N_TIME_POINTS, model_kind: str = 'random_forest', output_root: Path = SURROGATES_ROOT, random_state: int = 42)` | 46 | Train a model that predicts a resampled frame curve from case features. |

