function Constraints = add_storage_constraints(Constraints, vars, params)
%ADD_STORAGE_CONSTRAINTS CO2 and H2 inventory dynamics.

T = length(vars.F_CO2);
dtSeconds = params.model.dt_seconds;

Constraints = [Constraints, vars.S_CO2(1) == params.storage.initial_co2_fraction * vars.C_CO2];
Constraints = [Constraints, vars.S_H2(1) == params.storage.initial_h2_fraction * vars.C_H2];

for t = 1:T
    Constraints = [Constraints, ...
        vars.S_CO2(t + 1) == vars.S_CO2(t) + ...
        vars.m_CO2_prod(t) * dtSeconds - vars.F_CO2(t) * dtSeconds];
    Constraints = [Constraints, ...
        vars.S_H2(t + 1) == vars.S_H2(t) + ...
        vars.m_H2_prod(t) * dtSeconds - vars.F_H2(t) * dtSeconds];

    Constraints = [Constraints, ...
        vars.F_CO2(t) * dtSeconds <= vars.S_CO2(t) + vars.m_CO2_prod(t) * dtSeconds];
    Constraints = [Constraints, ...
        vars.F_H2(t) * dtSeconds <= vars.S_H2(t) + vars.m_H2_prod(t) * dtSeconds];
end

Constraints = [Constraints, vars.S_CO2 >= params.storage.co2_min_fraction * vars.C_CO2];
Constraints = [Constraints, vars.S_CO2 <= vars.C_CO2];
Constraints = [Constraints, vars.S_H2 >= params.storage.h2_min_fraction * vars.C_H2];
Constraints = [Constraints, vars.S_H2 <= vars.C_H2];

if isfield(params.storage, 'enforce_cyclic_terminal') && params.storage.enforce_cyclic_terminal
    Constraints = [Constraints, vars.S_CO2(T + 1) == vars.S_CO2(1)];
    Constraints = [Constraints, vars.S_H2(T + 1) == vars.S_H2(1)];
end
end
