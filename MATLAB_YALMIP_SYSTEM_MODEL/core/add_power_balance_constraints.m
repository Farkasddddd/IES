function Constraints = add_power_balance_constraints(Constraints, vars, pvPowerKw, params)
%ADD_POWER_BALANCE_CONSTRAINTS System electric power balance.

T = length(pvPowerKw);

Constraints = [Constraints, vars.P_grid >= 0, vars.P_curt >= 0];

if ~params.model.allow_grid
    Constraints = [Constraints, vars.P_grid == 0];
end

for t = 1:T
    Constraints = [Constraints, ...
        pvPowerKw(t) + vars.P_grid(t) + vars.P_dis(t) == ...
        vars.P_DAC(t) + vars.P_PEM(t) + vars.P_MeOH(t) + vars.P_ch(t) + vars.P_curt(t)];
end
end
