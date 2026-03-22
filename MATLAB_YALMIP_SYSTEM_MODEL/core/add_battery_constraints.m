function Constraints = add_battery_constraints(Constraints, vars, params)
%ADD_BATTERY_CONSTRAINTS Battery inventory and charge/discharge exclusivity.

T = length(vars.P_ch);
dtHours = params.model.dt_hours;
bigM = params.bounds.C_batP(2);

Constraints = [Constraints, vars.P_ch >= 0, vars.P_dis >= 0, vars.E_bat >= 0];
Constraints = [Constraints, vars.E_bat(1) == params.battery.initial_soc * vars.C_batE];

if isfield(params.battery, 'enable') && ~params.battery.enable
    Constraints = [Constraints, vars.C_batE == 0, vars.C_batP == 0];
    Constraints = [Constraints, vars.P_ch == 0, vars.P_dis == 0, vars.E_bat == 0, vars.z_bat == 0];
    return;
end

for t = 1:T
    Constraints = [Constraints, vars.P_ch(t) <= vars.C_batP];
    Constraints = [Constraints, vars.P_dis(t) <= vars.C_batP];

    if isfield(params.battery, 'enforce_exclusive') && params.battery.enforce_exclusive
        Constraints = [Constraints, vars.P_ch(t) <= bigM * vars.z_bat(t)];
        Constraints = [Constraints, vars.P_dis(t) <= bigM * (1 - vars.z_bat(t))];
    else
        Constraints = [Constraints, 0 <= vars.z_bat(t) <= 1];
    end

    Constraints = [Constraints, ...
        vars.E_bat(t + 1) == vars.E_bat(t) + ...
        params.battery.eta_ch * vars.P_ch(t) * dtHours - ...
        vars.P_dis(t) * dtHours / params.battery.eta_dis];
end

Constraints = [Constraints, vars.E_bat >= params.battery.soc_min * vars.C_batE];
Constraints = [Constraints, vars.E_bat <= params.battery.soc_max * vars.C_batE];

if isfield(params.battery, 'enforce_cyclic_terminal') && params.battery.enforce_cyclic_terminal
    Constraints = [Constraints, vars.E_bat(T + 1) == vars.E_bat(1)];
end
end
