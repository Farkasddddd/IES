function export_optimization_results(results, resultsDir)
%EXPORT_OPTIMIZATION_RESULTS Save summary and time series outputs.

if ~exist(resultsDir, 'dir')
    mkdir(resultsDir);
end

stamp = datestr(now, 'yyyymmdd_HHMMSS');
matPath = fullfile(resultsDir, ['optimization_result_', stamp, '.mat']);
csvPath = fullfile(resultsDir, ['optimization_timeseries_', stamp, '.csv']);
txtPath = fullfile(resultsDir, ['optimization_summary_', stamp, '.txt']);

save(matPath, 'results');

ts = results.timeseries;
tbl = table( ...
    ts.hour, ts.pv_kw, ts.P_DAC, ts.P_PEM, ts.P_MeOH, ts.P_grid, ts.P_curt, ...
    ts.P_ch, ts.P_dis, ts.CO2_prod_mol_s, ts.H2_prod_mol_s, ts.F_CO2_mol_s, ...
    ts.F_H2_mol_s, ts.MeOH_kg_h, ts.CO2_storage_mol, ts.H2_storage_mol, ...
    ts.Battery_energy_kWh, ts.n_ready, ts.n_sat, ts.n_ads, ts.n_des, ts.n_cool, ...
    'VariableNames', { ...
    'hour', 'pv_kw', 'P_DAC', 'P_PEM', 'P_MeOH', 'P_grid', 'P_curt', ...
    'P_ch', 'P_dis', 'CO2_prod_mol_s', 'H2_prod_mol_s', 'F_CO2_mol_s', ...
    'F_H2_mol_s', 'MeOH_kg_h', 'CO2_storage_mol', 'H2_storage_mol', ...
    'Battery_energy_kWh', 'n_ready', 'n_sat', 'n_ads', 'n_des', 'n_cool'});
writetable(tbl, csvPath);

fid = fopen(txtPath, 'w');
if fid > 0
    fprintf(fid, 'Objective mode: %s\n', results.objective.mode);
    fprintf(fid, 'Annual methanol (kg): %.6f\n', results.summary.annual_methanol_kg);
    fprintf(fid, 'Annual grid (kWh): %.6f\n', results.summary.annual_grid_kWh);
    fprintf(fid, 'Annual curtailment (kWh): %.6f\n', results.summary.annual_curtail_kWh);
    fprintf(fid, 'Annualized CAPEX (yuan): %.6f\n', results.summary.annualized_capex_yuan);
    fprintf(fid, 'Grid cost (yuan): %.6f\n', results.summary.grid_cost_yuan);
    fprintf(fid, 'Curtailment penalty (yuan): %.6f\n', results.summary.curtail_penalty_yuan);
    fprintf(fid, 'Methanol revenue (yuan): %.6f\n', results.summary.methanol_revenue_yuan);
    fprintf(fid, 'Objective value: %.6f\n', results.summary.objective_value);
    fclose(fid);
end
end
