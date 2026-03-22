function [Objective, meta] = build_objective(vars, pvPowerKw, econ, params)
%BUILD_OBJECTIVE Build the selected optimization objective.

dtHours = params.model.dt_hours;
horizonFraction = numel(pvPowerKw) / 8760.0;

pvNominalKw = max(pvPowerKw);
fixedPvCapex = pvNominalKw * econ.pv_cost_per_kw;
totalCapex = fixedPvCapex + ...
    econ.dac_cost_per_unit * vars.Ndac + ...
    econ.pem_cost_per_kw * vars.C_PEM + ...
    econ.battery_cost_per_kwh * vars.C_batE + ...
    econ.co2_tank_cost_per_mol * vars.C_CO2 + ...
    econ.h2_tank_cost_per_mol * vars.C_H2;

annualizedCapex = econ.crf * totalCapex;
periodCapex = annualizedCapex * horizonFraction;
gridCost = econ.grid_purchase_price_per_kwh * sum(vars.P_grid) * dtHours;
curtailmentCost = params.model.curtailment_penalty_yuan_per_kwh * sum(vars.P_curt) * dtHours;
methanolRevenue = params.model.methanol_price_yuan_per_kg * sum(vars.M) * dtHours;

modeName = lower(char(params.objective.mode));

switch modeName
    case 'max_methanol'
        Objective = -sum(vars.M) * dtHours;
        form = 'maximize methanol output';
    case 'max_profit'
        Objective = -(methanolRevenue - periodCapex - gridCost - curtailmentCost);
        form = 'maximize horizon profit';
    case 'weighted_cost_vs_methanol'
        Objective = params.objective.cost_weight * (periodCapex + gridCost + curtailmentCost) ...
            - params.objective.methanol_weight * sum(vars.M) * dtHours;
        form = 'weighted cost minus methanol';
    otherwise
        Objective = periodCapex + gridCost + curtailmentCost - methanolRevenue;
        form = 'minimize annualized total cost';
end

meta = struct();
meta.form = form;
meta.annualized_capex = annualizedCapex;
meta.period_capex = periodCapex;
meta.grid_cost = gridCost;
meta.curtailment_cost = curtailmentCost;
meta.methanol_revenue = methanolRevenue;
meta.annual_profit = methanolRevenue - periodCapex - gridCost - curtailmentCost;
meta.fixed_pv_capex = fixedPvCapex;
meta.pv_nominal_kw = pvNominalKw;
meta.horizon_fraction = horizonFraction;
end
