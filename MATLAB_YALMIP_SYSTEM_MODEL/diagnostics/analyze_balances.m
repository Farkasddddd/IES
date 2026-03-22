function report = analyze_balances(results, params)
%ANALYZE_BALANCES Check material consistency and energy conservation.

ts = results.timeseries;
dtHours = params.model.dt_hours;
dtSeconds = params.model.dt_seconds;
T = numel(ts.hour);

co2Residual = zeros(T, 1);
h2Residual = zeros(T, 1);
batResidual = zeros(T, 1);
powerResidual = zeros(T, 1);

for t = 1:T
    co2Residual(t) = ts.CO2_storage_mol_all(t + 1) - ts.CO2_storage_mol_all(t) - ...
        dtSeconds * (ts.CO2_prod_mol_s(t) - ts.F_CO2_mol_s(t));
    h2Residual(t) = ts.H2_storage_mol_all(t + 1) - ts.H2_storage_mol_all(t) - ...
        dtSeconds * (ts.H2_prod_mol_s(t) - ts.F_H2_mol_s(t));
    batResidual(t) = ts.Battery_energy_kWh_all(t + 1) - ts.Battery_energy_kWh_all(t) - ...
        (params.battery.eta_ch * ts.P_ch(t) * dtHours - ...
        ts.P_dis(t) * dtHours / params.battery.eta_dis);
    powerResidual(t) = ts.pv_kw(t) + ts.P_grid(t) + ts.P_dis(t) - ...
        (ts.P_DAC(t) + ts.P_PEM(t) + ts.P_MeOH(t) + ts.P_ch(t) + ts.P_curt(t));
end

ratioResidual = ts.F_H2_mol_s - params.surrogate.fixed_ratio * ts.F_CO2_mol_s;

report = struct();
report.co2.max_abs_residual_mol = max(abs(co2Residual));
report.co2.sum_abs_residual_mol = sum(abs(co2Residual));
report.h2.max_abs_residual_mol = max(abs(h2Residual));
report.h2.sum_abs_residual_mol = sum(abs(h2Residual));
report.battery.max_abs_residual_kWh = max(abs(batResidual));
report.battery.sum_abs_residual_kWh = sum(abs(batResidual));
report.power.max_abs_residual_kW = max(abs(powerResidual));
report.power.sum_abs_residual_kW = sum(abs(powerResidual));
report.methanol_ratio.max_abs_residual_mol_s = max(abs(ratioResidual));
report.methanol_ratio.sum_abs_residual_mol_s = sum(abs(ratioResidual));

report.aggregate.co2_produced_mol = sum(ts.CO2_prod_mol_s) * dtSeconds;
report.aggregate.co2_fed_mol = sum(ts.F_CO2_mol_s) * dtSeconds;
report.aggregate.h2_produced_mol = sum(ts.H2_prod_mol_s) * dtSeconds;
report.aggregate.h2_fed_mol = sum(ts.F_H2_mol_s) * dtSeconds;
report.aggregate.methanol_kg = sum(ts.MeOH_kg_h) * dtHours;
report.aggregate.pv_energy_kWh = sum(ts.pv_kw) * dtHours;
report.aggregate.dac_energy_kWh = sum(ts.P_DAC) * dtHours;
report.aggregate.pem_energy_kWh = sum(ts.P_PEM) * dtHours;
report.aggregate.meoh_energy_kWh = sum(ts.P_MeOH) * dtHours;
report.aggregate.charge_energy_kWh = sum(ts.P_ch) * dtHours;
report.aggregate.discharge_energy_kWh = sum(ts.P_dis) * dtHours;
report.aggregate.curtail_energy_kWh = sum(ts.P_curt) * dtHours;
report.aggregate.grid_energy_kWh = sum(ts.P_grid) * dtHours;

report.initial_final.co2_initial_mol = ts.CO2_storage_mol_all(1);
report.initial_final.co2_final_mol = ts.CO2_storage_mol_all(end);
report.initial_final.h2_initial_mol = ts.H2_storage_mol_all(1);
report.initial_final.h2_final_mol = ts.H2_storage_mol_all(end);
report.initial_final.battery_initial_kWh = ts.Battery_energy_kWh_all(1);
report.initial_final.battery_final_kWh = ts.Battery_energy_kWh_all(end);

report.series = struct();
report.series.co2_residual_mol = co2Residual;
report.series.h2_residual_mol = h2Residual;
report.series.battery_residual_kWh = batResidual;
report.series.power_residual_kW = powerResidual;
report.series.h2_ratio_residual_mol_s = ratioResidual;
end
