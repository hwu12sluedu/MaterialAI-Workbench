# API 功能清单（自动生成）

> 本文件由 `tools/generate_api_inventory.py` 生成，用于保证教学文档覆盖全部公开函数与类。修改源码后重新运行脚本即可刷新。

## 统计

- 模块数：28
- 顶层公开函数：129
- 公开类：38
- 公开类方法：77

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

- 行号：57
- 说明：Define class for Materials including material parameters (attributes), constitutive relations (methods)

| 方法 | 行号 | 说明 |
|---|---:|---|
| `response(self, sig, epl, deps, CV, maxit = 50)` | 207 | Calculate non-linear material response to deformation defined by load step, |
| `calc_yf(self, sig, epl = None, accumulated_strain = 0.0, max_stress = 0.0, flag = 0.0, tex = None, ana = False, pred = False)` | 348 | Calculate yield function |
| `ML_full_yf(self, sig, epl = None, ld = None, accumulated_strain = 0.0, max_stress = 0.0, flag = 0.0, tex = None, verb = True)` | 414 | Calculate full ML yield function as distance of a single given stress |
| `find_yloc(self, x, su, epl = None, accumulated_strain = 0.0, max_stress = 0.0, flag = 0.0, tex = None)` | 518 | Function to expand unit stresses by factor and calculate yield |
| `find_yloc_scalar(self, x, su, epl = None, accumulated_strain = 0.0, max_stress = 0.0, flag = 0.0, tex = None)` | 547 | Function to expand unit stresses by factor and calculate yield |
| `calc_seq(self, sig)` | 576 | Calculate generalized equivalent stress from stress tensor; |
| `calc_seqB(self, sv)` | 678 | Calculate equivalent stress based on Yld2004-18p yield function |
| `calc_fgrad(self, sig, epl = None, seq = None, accumulated_strain = 0.0, max_stress = 0.0, flag = 0.0, tex = None, ana = False)` | 708 | Calculate gradient to yield surface. Three different methods can be used: (i) analytical gradient to Hill-like yield |
| `calc_hessian(self, sig, epl = None, seq = None, accumulated_strain = 0.0, max_stress = 0.0, flag = 0.0, tex = None, ana = False)` | 864 | Calculate hessian to yield surface. Supports so far only option (ii) hessian to ML yield function (default if ML yield |
| `get_sflow(self, epl)` | 978 | Calculate an estimate of the scalar flow stress (strength) of the material |
| `epl_dot(self, sig, epl, Cel, deps, accumulated_strain = 0.0, max_stress = 0.0, flag = 0.0, tex = None)` | 1013 | Calculate plastic strain increment relaxing stress back to yield locus; |
| `C_tan(self, sig, Cel, epl = None)` | 1061 | Calculate tangent stiffness relaxing stress back to yield locus; |
| `setup_yf_SVM(self, x, y_train, x_test = None, y_test = None, C = 15.0, gamma = 2.5, fs = 0.1, plot = False, cyl = False, gridsearch = False, cvals = None, gvals = None, verbose = 3)` | 1095 | Generic function call to setup and train the SVM yield function, for details see the specific functions |
| `setup_yf_SVM_6D(self, x, y_train, x_test = None, y_test = None, C = 10.0, gamma = 1.0, plot = False, gridsearch = False, cvals = None, gvals = None, verbose = 3, pca_dim = 10, metric = 'acc')` | 1113 | Initialize and train Support Vector Classifier (SVC) as machine learning (ML) yield function. Training and |
| `setup_yf_SVM_3D(self, x, y_train, x_test = None, y_test = None, C = 10.0, gamma = 1.0, fs = 0.1, plot = False, cyl = False, gridsearch = False, cvals = None, gvals = None, pca_dim = 10)` | 1284 | Initialize and train Support Vector Classifier (SVC) as machine |
| `train_SVC(self, C = 10, gamma = 4, Nlc = 36, Nseq = 25, fs = 0.3, extend = False, mat_ref = None, sdata = None, plot = False, fontsize = 16, gridsearch = False, cvals = None, gvals = None, Fe = 0.1, Ce = 0.99, scaler = None, pca = None, train_index = None, test_index = None, verbose = 1, metric = 'acc', pca_dim = 10, reversal = None)` | 1446 | Train SVC for all yield functions of the microstructures provided |
| `test_data_generation(self, C = 10, gamma = 4, Nlc = 36, Nseq = 25, fs = 0.3, extend = False, mat_ref = None, sdata = None, fontsize = 16, gridsearch = False, cvals = None, gvals = None, Fe = 0.1, Ce = 0.99, reversal = False)` | 1827 | A function to generate test data to get the scores, which is exactly as we are generating |
| `create_sig_data(self, N = None, mat_ref = None, sdata = None, Nseq = 2, sflow = None, offs = 0.01, extend = False, rand = False, Fe = 0.1, Ce = 0.99)` | 1954 | Function to create consistent data sets on the deviatoric stress plane |
| `setup_fgrad_SVM(self)` | 2062 | Inititalize and train SVM regression on plastic strain increments in data |
| `export_MLparam(self, sname, source = None, file = None, path = '../../models/', descr = None, param = None)` | 2137 | The parameters of the trained Ml flow rule (support vectors, dual |
| `pckl(self, name = None, path = '../../materials/')` | 2279 | Write material into pickle file. Usefull for materials with trained machine |
| `create_scaled_input(self, sig, epl = None, acc_strain = None, max_stress = None, flag = None, tex = None)` | 2305 | Transforms np.array x to be used by SVM. |
| `GridSearchCVTexture(self, x, param_grid, n_splits, verbose = True)` | 2374 | Function to perform Grid Search Cross Validation over the textures. The difference compared to standard grid |
| `elasticity(self, C11 = None, C12 = None, C44 = None, CV = None, E = None, nu = None)` | 2405 | Define elastic material properties |
| `plasticity(self, sy = None, sdim = 6, drucker = 0.0, khard = 0.0, tresca = False, barlat = None, barlat_exp = None, hill = None, hill_3p = None, hill_6p = None, rv = None, lhs = None)` | 2470 | Define plastic material parameters; anisotropic Hill-like and Drucker-like |
| `from_data(self, param)` | 2602 | Define material properties from data sets generated in module `Data`: |
| `from_MLparam(self, name, path = '../../models/')` | 2694 | Define material properties from parameters of trained machine learning |
| `set_texture(self, current, verb = False)` | 2711 | Set parameters for current crystallographic texture of material as defined in microstructure. |
| `ellipsis(self, a = 1.0, b = 1.0 / np.sqrt(3.0), n = 72)` | 2778 | Create ellipsis with main axis along 45° axis, used for graphical representation of isotropic yield locus. |
| `plot_data(self, Z, axs, xx, yy, field = True, c = 'red')` | 2800 | Plotting data in stress space to visualize yield loci. |
| `plot_yield_locus(self, fun = None, label = None, data = None, trange = 0.01, peeq = 0.0, xstart = None, xend = None, axis1 = [0], axis2 = [1], iso = False, ref_mat = None, field = False, Nmesh = 100, file = None, fontsize = 20, scaling = True)` | 2841 | Plot different cuts through yield locus in 3D principal stress space. |
| `calc_properties(self, size = 2, Nel = 2, verb = False, eps = 0.005, min_step = None, sigeps = False, load_cases = ['stx', 'sty', 'et2', 'ect'])` | 3068 | Use pylabfea.model to calculate material strength and stress-strain |
| `plot_stress_strain(self, Hill = False, file = None, fontsize = 14)` | 3174 | Plot stress-strain data and print values for strength. Requires |
| `polar_plot_yl(self, Na = 72, cmat = None, data = None, dname = 'reference', scaling = None, field = False, predict = False, cbar = False, Np = 100, file = None, arrow = False, sJ2 = False, show = True)` | 3226 | Plot yield locus as polar plot in deviatoric stress plane |


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
- 模块说明：Material AI Workbench prototype built on top of pyLabFEA.

## `material_ai_workbench.abaqus_batch_client`

- 文件：`material_ai_workbench/abaqus_batch_client.py`
- 模块说明：Batch Abaqus Python helpers for ODB post-processing.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `extract_odb_field_summary_batch(odb_path: Path \| str, *, fields: list[str] \| tuple[str, ...] \| None = None, max_values_per_field: int = 500000, max_history_outputs: int = 200, output_dir: Path \| str \| None = None, config: AbaqusBatchConfig \| None = None)` | 31 | Extract final-frame ODB field statistics with Abaqus SMAPython. |
| `extract_odb_frame_series_batch(odb_path: Path \| str, *, fields: list[str] \| tuple[str, ...] \| None = None, region_names: list[str] \| tuple[str, ...] \| None = None, max_values_per_field: int = 200000, max_frames_per_step: int = 500, output_dir: Path \| str \| None = None, config: AbaqusBatchConfig \| None = None)` | 94 | Extract per-frame aggregate curves from an ODB with Abaqus SMAPython. |

### 类与方法

#### `AbaqusBatchError(RuntimeError)`

- 行号：21
- 说明：Raised when an Abaqus batch post-processing command fails.

#### `AbaqusBatchConfig`

- 行号：26


## `material_ai_workbench.abaqus_bridge`

- 文件：`material_ai_workbench/abaqus_bridge.py`
- 模块说明：Prepare and optionally run Abaqus UMAT verification for a Workbench run.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `prepare_abaqus_verification(config: AbaqusBridgeConfig)` | 46 | 待补充 |
| `run_abaqus_verification(config: AbaqusBridgeConfig)` | 90 | 待补充 |
| `main()` | 168 | 待补充 |

### 类与方法

#### `AbaqusBridgeConfig`

- 行号：22

#### `AbaqusBridgeResult`

- 行号：33


## `material_ai_workbench.abaqus_mcp_client`

- 文件：`material_ai_workbench/abaqus_mcp_client.py`
- 模块说明：Direct client for the Abaqus MCP socket bridge.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `request_bridge(method: str, params: dict[str, Any] \| None = None, config: AbaqusMcpConfig \| None = None)` | 62 | Send one request to the Abaqus GUI socket bridge. |
| `ping_bridge(config: AbaqusMcpConfig \| None = None)` | 105 | Return a user-facing connection status. |
| `execute_kernel_code(code: str, config: AbaqusMcpConfig \| None = None)` | 150 | Execute a small Python chunk inside the live Abaqus/CAE kernel. |
| `stop_bridge(config: AbaqusMcpConfig \| None = None)` | 161 | Request the Abaqus MCP socket bridge to stop. |
| `set_workdir(path: Path \| str, config: AbaqusMcpConfig \| None = None)` | 171 | 待补充 |
| `get_model_info(config: AbaqusMcpConfig \| None = None)` | 185 | 待补充 |
| `list_jobs(config: AbaqusMcpConfig \| None = None)` | 247 | 待补充 |
| `monitor_job_status(job_name: str = '', config: AbaqusMcpConfig \| None = None)` | 267 | 待补充 |
| `submit_job(job_name: str, config: AbaqusMcpConfig \| None = None)` | 323 | 待补充 |
| `inspect_odb(odb_path: Path \| str, config: AbaqusMcpConfig \| None = None)` | 339 | 待补充 |
| `extract_odb_field_summary(odb_path: Path \| str, *, fields: list[str] \| tuple[str, ...] \| None = None, max_values_per_field: int = 500000, max_history_outputs: int = 200, config: AbaqusMcpConfig \| None = None)` | 404 | Extract final-frame field statistics from an ODB through Abaqus/CAE. |
| `display_odb_contour(odb_path: Path \| str, *, field_label: str = 'S', invariant: str = 'Mises', output_position: str = 'INTEGRATION_POINT', config: AbaqusMcpConfig \| None = None)` | 668 | Display an ODB contour in the current Abaqus viewport before capture. |
| `capture_viewport(output_dir: Path \| str, viewport_name: str = '', image_format: str = 'PNG', config: AbaqusMcpConfig \| None = None)` | 743 | 待补充 |
| `create_session_snapshot(selected_run: Path \| None = None, config: AbaqusMcpConfig \| None = None, capture_image: bool = True)` | 801 | Capture status/model/job/viewport information into a local report folder. |

### 类与方法

#### `AbaqusMcpError(RuntimeError)`

- 行号：28
- 说明：Raised when the Abaqus MCP bridge cannot complete a request.

#### `AbaqusMcpConnectionError(AbaqusMcpError)`

- 行号：32
- 说明：Raised when the Abaqus MCP bridge endpoint is unreachable.

#### `AbaqusMcpConfig`

- 行号：37

#### `AbaqusMcpStatus`

- 行号：44

#### `AbaqusMcpSnapshot`

- 行号：54


## `material_ai_workbench.batch_simulation`

- 文件：`material_ai_workbench/batch_simulation.py`
- 模块说明：Batch simulation planning and execution for MaterialAI Workbench.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `create_parameter_sweep_plan(*, name: str = 'batch_j2_sweep', material_type: str = 'j2', yield_strengths: list[float] \| tuple[float, ...] = DEFAULT_YIELD_STRENGTHS, youngs_modulus: float = 200000.0, poisson_ratio: float = 0.3, hill_ratios: tuple[float, float, float, float, float, float] = DEFAULT_HILL_RATIOS, c_value: float = 1.0, gamma: float = 1.0, n_load_cases: int = 32, n_sequence: int = 3, test_size: int = 60, plot_mesh: int = 40, max_abaqus_load_cases: int = 1, output_root: Path = BATCH_ROOT)` | 54 | Create a small batch plan for material-parameter sample expansion. |
| `load_batch_plan(plan_dir: Path \| str)` | 125 | Load a batch plan folder or batch_plan.json file. |
| `save_batch_plan(plan: BatchPlan)` | 134 | 待补充 |
| `list_batch_plans(root: Path = BATCH_ROOT)` | 144 | Return batch plan folders, newest first. |
| `run_batch_plan(plan_dir: Path \| str, *, run_abaqus: bool = False, archive_cases: bool = False, postprocess_odb: bool = False, export_dataset_after: bool = False, train_surrogate_after: bool = False, max_samples: int \| None = None, timeout_seconds: int = 1800)` | 153 | Run pending/failed samples in a batch plan. |
| `batch_sample_table_rows(plan: BatchPlan \| dict[str, Any])` | 208 | Return compact rows for Streamlit and reports. |

### 类与方法

#### `BatchPlan`

- 行号：42

| 方法 | 行号 | 说明 |
|---|---:|---|
| `samples(self)` | 50 | 待补充 |


## `material_ai_workbench.case_library`

- 文件：`material_ai_workbench/case_library.py`
- 模块说明：Abaqus case-library utilities for MaterialAI Workbench.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `scan_case_folder(source_folder: Path \| str, *, title: str, tags: list[str] \| str \| None = None, description: str = '', status: str = 'success', parameters: dict[str, Any] \| None = None, lessons_learned: str = '', next_actions: str = '', cases_root: Path = CASES_ROOT)` | 97 | 待补充 |
| `save_case_summary(summary: CaseSummary)` | 150 | 待补充 |
| `write_case_report(summary: CaseSummary)` | 159 | 待补充 |
| `list_cases(cases_root: Path = CASES_ROOT)` | 167 | 待补充 |
| `load_case_summary(case_dir: Path \| str)` | 179 | 待补充 |
| `case_table_rows(cases: list[CaseSummary])` | 188 | 待补充 |
| `file_table_rows(summary: CaseSummary, category: str \| None = None)` | 208 | 待补充 |
| `inp_feature_table_rows(summary: CaseSummary)` | 227 | 待补充 |
| `result_feature_table_rows(summary: CaseSummary)` | 246 | 待补充 |
| `odb_extraction_table_rows(summary: CaseSummary)` | 290 | 待补充 |
| `odb_frame_series_table_rows(summary: CaseSummary)` | 309 | 待补充 |
| `append_odb_extraction(summary: CaseSummary, extraction: dict[str, Any])` | 327 | 待补充 |
| `append_odb_frame_series(summary: CaseSummary, series: dict[str, Any])` | 334 | 待补充 |
| `extract_inp_features(inp_path: Path \| str)` | 341 | 待补充 |
| `extract_csv_result_features(csv_path: Path \| str)` | 350 | 待补充 |

### 类与方法

#### `CaseFile`

- 行号：63

#### `CaseSummary`

- 行号：74


## `material_ai_workbench.closed_loop_report`

- 文件：`material_ai_workbench/closed_loop_report.py`
- 模块说明：Closed-loop validation report utilities for MaterialAI Workbench.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `generate_closed_loop_report(*, material_run: Path \| str \| None = None, case_dir: Path \| str \| None = None, dataset_dir: Path \| str \| None = None, surrogate_run: Path \| str \| None = None, batch_plan: Path \| str \| None = None, output_root: Path = CLOSED_LOOP_ROOT)` | 31 | Generate a Markdown report that links the MVP CAE + AI loop together. |
| `list_closed_loop_reports(root: Path = CLOSED_LOOP_ROOT)` | 101 | Return generated closed-loop report folders, newest first. |

### 类与方法

#### `ClosedLoopReport`

- 行号：24


## `material_ai_workbench.composite_dataset`

- 文件：`material_ai_workbench/composite_dataset.py`
- 模块说明：Composite RVE dataset and surrogate utilities.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `create_composite_batch_plan(config: CompositeBatchConfig)` | 97 | 待补充 |
| `list_composite_batch_plans(root: Path = COMPOSITE_BATCH_ROOT)` | 123 | 待补充 |
| `load_composite_batch_plan(plan_dir: Path \| str)` | 133 | 待补充 |
| `run_composite_batch_plan(plan_dir: Path \| str, *, max_samples: int \| None = None)` | 148 | 待补充 |
| `build_composite_dataset(plan_dir: Path \| str, output_csv: Path \| str \| None = None)` | 180 | 待补充 |
| `train_composite_surrogate(dataset_csv: Path \| str, *, target_column: str = DEFAULT_COMPOSITE_TARGET, model_kind: str = 'random_forest', output_root: Path = COMPOSITE_SURROGATE_ROOT, random_state: int = 42)` | 201 | 待补充 |

### 类与方法

#### `CompositeBatchConfig`

- 行号：49

#### `CompositeBatchPlan`

- 行号：77

#### `CompositeSurrogateRun`

- 行号：87


## `material_ai_workbench.composite_workflow`

- 文件：`material_ai_workbench/composite_workflow.py`
- 模块说明：Composite micro-to-macro workflow for a 3D Abaqus plate-with-hole case.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `run_composite_plate_workflow(config: CompositePlateConfig)` | 88 | 待补充 |
| `compute_effective_ud_properties(config: CompositePlateConfig)` | 202 | 待补充 |
| `build_pylabfea_material_summary(config: CompositePlateConfig, props: dict[str, float])` | 240 | 待补充 |
| `estimate_plate_response(config: CompositePlateConfig, props: dict[str, float])` | 282 | 待补充 |
| `list_composite_runs(root: Path = COMPOSITE_ROOT)` | 308 | 待补充 |
| `load_composite_manifest(run_dir: Path \| str)` | 318 | 待补充 |
| `generate_fiber_layout(config: CompositePlateConfig)` | 322 | 待补充 |
| `write_microstructure_preview(path: Path, config: CompositePlateConfig, layout: dict[str, Any])` | 363 | 待补充 |
| `write_micro_rve_inp(path: Path, phase_map_path: Path, config: CompositePlateConfig, layout: dict[str, Any])` | 397 | 待补充 |
| `micro_rve_load_cases(config: CompositePlateConfig)` | 559 | 待补充 |
| `write_micro_rve_pbc_jobs(job_dir: Path, config: CompositePlateConfig, layout: dict[str, Any])` | 571 | 待补充 |
| `write_micro_pbc_plan(path: Path, config: CompositePlateConfig, jobs: dict[str, Path])` | 740 | 待补充 |
| `write_micro_pbc_run_script(path: Path, config: CompositePlateConfig, job_dir: Path, jobs: dict[str, Path])` | 758 | 待补充 |
| `write_micro_pbc_postprocess_script(path: Path, config: CompositePlateConfig, job_dir: Path)` | 769 | 待补充 |
| `write_micro_rve_run_script(path: Path, config: CompositePlateConfig, micro_inp: Path, run_dir: Path)` | 853 | 待补充 |
| `write_plate_preview(path: Path, config: CompositePlateConfig, estimates: dict[str, float])` | 862 | 待补充 |
| `write_material_card(path: Path, props: dict[str, float])` | 890 | 待补充 |
| `write_abaqus_build_script(path: Path, config: CompositePlateConfig, props: dict[str, float], run_dir: Path)` | 903 | 待补充 |
| `write_odb_postprocess_script(path: Path, config: CompositePlateConfig, run_dir: Path)` | 1007 | 待补充 |
| `write_run_script(path: Path, config: CompositePlateConfig, abaqus_script: Path, post_script: Path, run_dir: Path)` | 1050 | 待补充 |
| `write_dataset_row(path: Path, config: CompositePlateConfig, props: dict[str, float], estimates: dict[str, float], micro_metrics: dict[str, float])` | 1067 | 待补充 |
| `run_abaqus_build(config: CompositePlateConfig, abaqus_script: Path, run_dir: Path)` | 1102 | 待补充 |

### 类与方法

#### `CompositePlateConfig`

- 行号：28

#### `CompositePlateResult`

- 行号：62


## `material_ai_workbench.data_import`

- 文件：`material_ai_workbench/data_import.py`
- 模块说明：CSV import utilities for material curves and Abaqus batch results.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `import_csv_dataset(*, source_path: Path \| None = None, source_bytes: bytes \| None = None, source_name: str = 'uploaded.csv', source_kind: str = 'experiment_curve', material_name: str = 'imported_material', imports_root: Path = IMPORTS_ROOT)` | 45 | 待补充 |
| `list_imports(imports_root: Path = IMPORTS_ROOT)` | 121 | 待补充 |
| `load_import_summary(import_dir: Path)` | 131 | 待补充 |
| `read_normalized_preview(path: Path, limit: int = 30)` | 135 | 待补充 |

### 类与方法

#### `DataImportResult`

- 行号：27


## `material_ai_workbench.dataset_export`

- 文件：`material_ai_workbench/dataset_export.py`
- 模块说明：Dataset export utilities for the MaterialAI Workbench case library.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `export_case_dataset(*, cases_root: Path = CASES_ROOT, output_root: Path = DATASETS_ROOT, name: str = 'case_dataset', case_dirs: list[Path \| str] \| tuple[Path \| str, ...] \| None = None)` | 30 | Export case-library features into CSV assets for ML experiments. |

### 类与方法

#### `DatasetExport`

- 行号：19


## `material_ai_workbench.llm_adapter`

- 文件：`material_ai_workbench/llm_adapter.py`
- 模块说明：Optional LLM adapter for natural-language simulation planning.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `plan_task_with_llm(prompt: str, config: LlmChatConfig, transport: Transport \| None = None)` | 64 | Call an OpenAI-compatible chat endpoint and parse a task JSON response. |

### 类与方法

#### `LlmConfigError(RuntimeError)`

- 行号：20
- 说明：Raised when an LLM request is not configured enough to run.

#### `LlmResponseError(RuntimeError)`

- 行号：24
- 说明：Raised when the LLM response cannot be converted into a task JSON.

#### `LlmChatConfig`

- 行号：29

| 方法 | 行号 | 说明 |
|---|---:|---|
| `api_key(self)` | 38 | 待补充 |
| `validate(self)` | 41 | 待补充 |
| `to_public_dict(self)` | 49 | 待补充 |

#### `LlmTaskPlan`

- 行号：57


## `material_ai_workbench.material_library`

- 文件：`material_ai_workbench/material_library.py`
- 模块说明：JSON-backed material preset library for MaterialAI Workbench.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `load_material_presets()` | 46 | 待补充 |
| `save_material_preset(preset: MaterialPreset)` | 56 | 待补充 |
| `delete_material_preset(name: str)` | 63 | 待补充 |
| `ensure_material_library()` | 69 | 待补充 |
| `preset_to_training_state(preset: MaterialPreset)` | 104 | 待补充 |
| `preset_from_training_state(name: str, state: dict[str, Any], notes: str = '')` | 123 | 待补充 |

### 类与方法

#### `MaterialPreset`

- 行号：17

| 方法 | 行号 | 说明 |
|---|---:|---|
| `normalized(self)` | 35 | 待补充 |


## `material_ai_workbench.nl_tasks`

- 文件：`material_ai_workbench/nl_tasks.py`
- 模块说明：Rule-based natural-language task parser for MaterialAI Workbench v0.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `parse_natural_language_task(text: str)` | 65 | 待补充 |
| `task_from_dict(payload: dict[str, Any], source_text: str = '')` | 139 | Convert a structured task JSON into the internal task dataclasses. |
| `task_to_workbench_config(task: ParsedSimulationTask, output_dir: Path)` | 187 | 待补充 |

### 类与方法

#### `MaterialTaskSpec`

- 行号：18

#### `MLTaskSpec`

- 行号：28

#### `AbaqusTaskSpec`

- 行号：40

#### `ParsedSimulationTask`

- 行号：47

| 方法 | 行号 | 说明 |
|---|---:|---|
| `to_dict(self)` | 56 | 待补充 |
| `to_json(self)` | 61 | 待补充 |


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

## `material_ai_workbench.pipeline`

- 文件：`material_ai_workbench/pipeline.py`
- 模块说明：End-to-end material ML training workflow for the first Workbench prototype.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `run_material_workbench(config: WorkbenchConfig)` | 76 | 待补充 |

### 类与方法

#### `WorkbenchConfig`

- 行号：31

#### `WorkbenchResult`

- 行号：63


## `material_ai_workbench.run_composite_batch`

- 文件：`material_ai_workbench/run_composite_batch.py`
- 模块说明：Command-line tools for composite RVE batch data and surrogate training.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `main()` | 16 | 待补充 |

## `material_ai_workbench.run_composite_workflow`

- 文件：`material_ai_workbench/run_composite_workflow.py`
- 模块说明：Command-line entry point for the composite 3D plate-with-hole workflow.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `main()` | 11 | 待补充 |

## `material_ai_workbench.run_workbench`

- 文件：`material_ai_workbench/run_workbench.py`
- 模块说明：Command line entry point for the MaterialAI Workbench prototype.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `main()` | 11 | 待补充 |

## `material_ai_workbench.streamlit_app`

- 文件：`material_ai_workbench/streamlit_app.py`
- 模块说明：Streamlit front end for the MaterialAI Workbench prototype.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `main()` | 124 | 待补充 |

## `material_ai_workbench.surrogate_model`

- 文件：`material_ai_workbench/surrogate_model.py`
- 模块说明：Surrogate-model training utilities for case-library datasets.

### 顶层函数

| 函数 | 行号 | 说明 |
|---|---:|---|
| `list_dataset_exports(root: Path = DATASETS_ROOT)` | 84 | Return dataset export folders that contain case_dataset.csv. |
| `list_surrogate_runs(root: Path = SURROGATES_ROOT)` | 96 | Return surrogate-model run folders, newest first. |
| `surrogate_comparison_rows(runs: Iterable[Path \| str] \| None = None, *, dataset_dir: Path \| str \| None = None, target_column: str \| None = None)` | 105 | Build compact comparison rows from surrogate_metrics.json files. |
| `train_surrogate_from_dataset(dataset_dir: Path \| str, *, target_column: str = DEFAULT_TARGET, model_kind: str = 'random_forest', output_root: Path = SURROGATES_ROOT, random_state: int = 42)` | 154 | Train a small surrogate model from a case-dataset export. |

### 类与方法

#### `SurrogateRun`

- 行号：72


