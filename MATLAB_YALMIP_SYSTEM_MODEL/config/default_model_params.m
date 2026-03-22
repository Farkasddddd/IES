function params = default_model_params(modelRoot)
%DEFAULT_MODEL_PARAMS Default configuration for the YALMIP system model.

repoRoot = fileparts(modelRoot);

params = struct();

params.paths = struct();
params.paths.repo_root = repoRoot;
params.paths.model_root = modelRoot;
params.paths.pv_csv = fullfile(repoRoot, 'data', 'pvwatts_hourly_shanghai.csv');
params.paths.methanol_excel = fullfile(repoRoot, 'data', 'Methanol_IES_AutoSave_Updated.xlsx');
params.paths.economic_params_py = fullfile(repoRoot, 'RL_capacity_optimization', 'config', 'economic_params.py');
params.paths.results_dir = fullfile(modelRoot, 'results');

params.model = struct();
params.model.dt_hours = 1.0;
params.model.dt_seconds = 3600.0;
params.model.horizon_steps = 8760;
params.model.pv_scale = 1.0;
params.model.allow_grid = true;
params.model.curtailment_penalty_yuan_per_kwh = 0.0;
params.model.methanol_price_yuan_per_kg = 6.0;
params.model.relax_integer_counts = true;

params.bounds = struct();
params.bounds.Ndac = [10, 500];
params.bounds.C_PEM = [100, 3000];
params.bounds.C_batE = [0, 10000];
params.bounds.C_batP = [0, 5000];
params.bounds.C_CO2 = [0, 5e7];
params.bounds.C_H2 = [0, 5e7];

params.dac = struct();
params.dac.tau_ads = 2;
params.dac.tau_des = 1;
params.dac.tau_cool = 1;
params.dac.p_fan_kw_per_unit = 0.05;
params.dac.p_heat_kw_per_unit = 1.0;
params.dac.co2_prod_mol_s_per_unit = 0.0367 / 60.0;
params.dac.initial_ready_fraction = 1.0;
params.dac.initial_saturated_fraction = 0.0;

params.pem = struct();
params.pem.max_load = 1.20;
params.pem.h2_prod_mol_s_per_kw = (1000.0 * 0.70) / 286000.0;

params.battery = struct();
params.battery.eta_ch = 0.95;
params.battery.eta_dis = 0.95;
params.battery.initial_soc = 0.50;
params.battery.soc_min = 0.10;
params.battery.soc_max = 0.90;
params.battery.max_c_rate = 1.0;
params.battery.enforce_cyclic_terminal = false;
params.battery.enable = true;
params.battery.enforce_exclusive = true;

params.storage = struct();
params.storage.initial_co2_fraction = 0.50;
params.storage.initial_h2_fraction = 0.50;
params.storage.co2_min_fraction = 0.00;
params.storage.h2_min_fraction = 0.00;
params.storage.enforce_cyclic_terminal = false;

params.surrogate = struct();
params.surrogate.fixed_ratio = 3.0;
params.surrogate.ratio_tolerance = 0.15;
params.surrogate.n_breakpoints = 12;
params.surrogate.min_feed_co2_mol_s = 0.01;
params.surrogate.max_feed_co2_mol_s = 0.15;
params.surrogate.enforce_continuous_operation = true;
params.surrogate.enforce_startup_then_continuous = false;
params.surrogate.min_on_hours = 0;
params.surrogate.always_on = true;

params.objective = struct();
params.objective.mode = 'max_profit';
params.objective.methanol_weight = 1.0;
params.objective.cost_weight = 1.0;

params.solver = struct();
params.solver.name = 'gurobi';
params.solver.verbose = 1;
end
