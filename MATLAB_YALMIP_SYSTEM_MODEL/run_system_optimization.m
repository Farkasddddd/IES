function results = run_system_optimization(params)
%RUN_SYSTEM_OPTIMIZATION Main entry for the MATLAB/YALMIP IES model.

modelRoot = fileparts(mfilename('fullpath'));
setup_matlab_paths;

if nargin < 1 || isempty(params)
params = default_model_params(modelRoot);
end

econ = load_codex_folder('economic_params', modelRoot);
market = load_codex_folder('market_scenarios', modelRoot);

if (~isfield(params.model, 'methanol_price_yuan_per_kg')) || isempty(params.model.methanol_price_yuan_per_kg)
    params.model.methanol_price_yuan_per_kg = market.default.methanol_price_yuan_per_kg;
end

pvPowerKw = load_pv_profile(params.paths.pv_csv, params.model.pv_scale);
T = min(params.model.horizon_steps, numel(pvPowerKw));
pvPowerKw = pvPowerKw(1:T);

methanolLookup = build_methanol_lookup( ...
    params.paths.methanol_excel, ...
    params.surrogate.fixed_ratio, ...
    params.surrogate.ratio_tolerance, ...
    params.surrogate.n_breakpoints);

vars = struct();

if isfield(params.model, 'relax_integer_counts') && params.model.relax_integer_counts
    vars.Ndac = sdpvar(1, 1);
    vars.n_ready = sdpvar(T + 1, 1);
    vars.n_sat = sdpvar(T + 1, 1);
    vars.n_ads = sdpvar(T, 1);
    vars.n_des = sdpvar(T, 1);
    vars.n_cool = sdpvar(T, 1);
    vars.u_ads = sdpvar(T, 1);
    vars.u_des = sdpvar(T, 1);
    vars.u_cool = sdpvar(T, 1);
else
    vars.Ndac = intvar(1, 1);
    vars.n_ready = intvar(T + 1, 1);
    vars.n_sat = intvar(T + 1, 1);
    vars.n_ads = intvar(T, 1);
    vars.n_des = intvar(T, 1);
    vars.n_cool = intvar(T, 1);
    vars.u_ads = intvar(T, 1);
    vars.u_des = intvar(T, 1);
    vars.u_cool = intvar(T, 1);
end

vars.C_PEM = sdpvar(1, 1);
vars.C_batE = sdpvar(1, 1);
vars.C_batP = sdpvar(1, 1);
vars.C_CO2 = sdpvar(1, 1);
vars.C_H2 = sdpvar(1, 1);

vars.P_DAC = sdpvar(T, 1);
vars.m_CO2_prod = sdpvar(T, 1);

vars.P_PEM = sdpvar(T, 1);
vars.m_H2_prod = sdpvar(T, 1);

vars.F_CO2 = sdpvar(T, 1);
vars.F_H2 = sdpvar(T, 1);
vars.M = sdpvar(T, 1);
vars.P_MeOH = sdpvar(T, 1);
if isfield(params.surrogate, 'always_on') && params.surrogate.always_on && ...
        ~(isfield(params.surrogate, 'enforce_startup_then_continuous') && params.surrogate.enforce_startup_then_continuous)
    vars.z_MeOH_on = sdpvar(T, 1);
else
    vars.z_MeOH_on = binvar(T, 1);
end

vars.E_bat = sdpvar(T + 1, 1);
vars.P_ch = sdpvar(T, 1);
vars.P_dis = sdpvar(T, 1);
if isfield(params.battery, 'enforce_exclusive') && params.battery.enforce_exclusive
    vars.z_bat = binvar(T, 1);
else
    vars.z_bat = sdpvar(T, 1);
end

vars.S_CO2 = sdpvar(T + 1, 1);
vars.S_H2 = sdpvar(T + 1, 1);

vars.P_grid = sdpvar(T, 1);
vars.P_curt = sdpvar(T, 1);

Constraints = [];

Constraints = [Constraints, params.bounds.Ndac(1) <= vars.Ndac <= params.bounds.Ndac(2)];
Constraints = [Constraints, params.bounds.C_PEM(1) <= vars.C_PEM <= params.bounds.C_PEM(2)];
Constraints = [Constraints, params.bounds.C_batE(1) <= vars.C_batE <= params.bounds.C_batE(2)];
Constraints = [Constraints, params.bounds.C_batP(1) <= vars.C_batP <= params.bounds.C_batP(2)];
Constraints = [Constraints, params.bounds.C_CO2(1) <= vars.C_CO2 <= params.bounds.C_CO2(2)];
Constraints = [Constraints, params.bounds.C_H2(1) <= vars.C_H2 <= params.bounds.C_H2(2)];
Constraints = [Constraints, vars.C_batP <= params.battery.max_c_rate * vars.C_batE];

[Constraints, dacAux] = add_dac_constraints(Constraints, vars, params);
[Constraints, pemAux] = add_pem_constraints(Constraints, vars, params);
Constraints = add_methanol_surrogate_constraints(Constraints, vars, methanolLookup, params);
Constraints = add_storage_constraints(Constraints, vars, params);
Constraints = add_battery_constraints(Constraints, vars, params);
Constraints = add_power_balance_constraints(Constraints, vars, pvPowerKw, params);

[Objective, objectiveMeta] = build_objective(vars, pvPowerKw, econ, params);

options = sdpsettings('solver', params.solver.name, 'verbose', params.solver.verbose);
sol = optimize(Constraints, Objective, options);

results = struct();
results.solver.problem = sol.problem;
results.solver.info = sol.info;
results.solver.message = yalmiperror(sol.problem);
results.objective.mode = params.objective.mode;
results.objective.form = objectiveMeta.form;

if sol.problem ~= 0
    warning('Optimization did not finish successfully: %s', results.solver.message);
    return;
end

results.capacity.Ndac = value(vars.Ndac);
results.capacity.C_PEM = value(vars.C_PEM);
results.capacity.C_batE = value(vars.C_batE);
results.capacity.C_batP = value(vars.C_batP);
results.capacity.C_CO2 = value(vars.C_CO2);
results.capacity.C_H2 = value(vars.C_H2);

results.timeseries.hour = (1:T).';
results.timeseries.pv_kw = pvPowerKw;
results.timeseries.P_DAC = value(vars.P_DAC);
results.timeseries.P_PEM = value(vars.P_PEM);
results.timeseries.P_MeOH = value(vars.P_MeOH);
results.timeseries.P_grid = value(vars.P_grid);
results.timeseries.P_curt = value(vars.P_curt);
results.timeseries.P_ch = value(vars.P_ch);
results.timeseries.P_dis = value(vars.P_dis);
results.timeseries.z_bat = value(vars.z_bat);
results.timeseries.CO2_prod_mol_s = value(vars.m_CO2_prod);
results.timeseries.H2_prod_mol_s = value(vars.m_H2_prod);
results.timeseries.F_CO2_mol_s = value(vars.F_CO2);
results.timeseries.F_H2_mol_s = value(vars.F_H2);
results.timeseries.MeOH_kg_h = value(vars.M);
results.timeseries.z_MeOH_on = value(vars.z_MeOH_on);
results.timeseries.CO2_storage_mol = value(vars.S_CO2(1:T));
results.timeseries.H2_storage_mol = value(vars.S_H2(1:T));
results.timeseries.Battery_energy_kWh = value(vars.E_bat(1:T));
results.timeseries.CO2_storage_mol_all = value(vars.S_CO2);
results.timeseries.H2_storage_mol_all = value(vars.S_H2);
results.timeseries.Battery_energy_kWh_all = value(vars.E_bat);
results.timeseries.n_ready = value(vars.n_ready(1:T));
results.timeseries.n_sat = value(vars.n_sat(1:T));
results.timeseries.n_ads = value(vars.n_ads);
results.timeseries.n_des = value(vars.n_des);
results.timeseries.n_cool = value(vars.n_cool);

results.summary.annual_methanol_kg = sum(results.timeseries.MeOH_kg_h) * params.model.dt_hours;
results.summary.annual_grid_kWh = sum(results.timeseries.P_grid) * params.model.dt_hours;
results.summary.annual_curtail_kWh = sum(results.timeseries.P_curt) * params.model.dt_hours;
results.summary.annualized_capex_yuan = value(objectiveMeta.annualized_capex);
results.summary.grid_cost_yuan = value(objectiveMeta.grid_cost);
results.summary.curtail_penalty_yuan = value(objectiveMeta.curtailment_cost);
results.summary.methanol_revenue_yuan = value(objectiveMeta.methanol_revenue);
results.summary.annual_profit_yuan = value(objectiveMeta.annual_profit);
results.summary.objective_value = value(Objective);
results.summary.dac = dacAux;
results.summary.pem = pemAux;
results.summary.methanol_lookup = methanolLookup.meta;
positiveFeeds = methanolLookup.feed_breakpoints(methanolLookup.feed_breakpoints > 0);
if isempty(params.surrogate.min_feed_co2_mol_s)
    results.summary.minimum_co2_feed_mol_s = min(positiveFeeds);
else
    results.summary.minimum_co2_feed_mol_s = params.surrogate.min_feed_co2_mol_s;
end
results.summary.methanol_price_yuan_per_kg = params.model.methanol_price_yuan_per_kg;

annualCost = results.summary.annualized_capex_yuan + ...
    results.summary.grid_cost_yuan + results.summary.curtail_penalty_yuan;
results.summary.lcom_yuan_per_kg = annualCost / max(results.summary.annual_methanol_kg, 1e-9);

export_optimization_results(results, params.paths.results_dir);

disp('Optimization finished successfully.');
disp(results.summary);
end
