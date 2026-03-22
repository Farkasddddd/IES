function [Constraints, aux] = add_dac_constraints(Constraints, vars, params)
%ADD_DAC_CONSTRAINTS Fixed-cycle DAC occupancy and production model.

T = length(vars.u_ads);
tauAds = params.dac.tau_ads;
tauDes = params.dac.tau_des;
tauCool = params.dac.tau_cool;

Constraints = [Constraints, vars.n_ready(1) == params.dac.initial_ready_fraction * vars.Ndac];
Constraints = [Constraints, vars.n_sat(1) == params.dac.initial_saturated_fraction * vars.Ndac];

Constraints = [Constraints, vars.u_ads >= 0, vars.u_des >= 0, vars.u_cool >= 0];
Constraints = [Constraints, vars.n_ads >= 0, vars.n_des >= 0, vars.n_cool >= 0];
Constraints = [Constraints, vars.n_ready >= 0, vars.n_sat >= 0];
Constraints = [Constraints, vars.P_DAC >= 0, vars.m_CO2_prod >= 0];

for t = 1:T
    activeAds = 0;
    for k = max(1, t - tauAds + 1):t
        activeAds = activeAds + vars.u_ads(k);
    end

    activeDes = 0;
    for k = max(1, t - tauDes + 1):t
        activeDes = activeDes + vars.u_des(k);
    end

    activeCool = 0;
    if t > tauDes
        for k = max(1, t - tauDes - tauCool + 1):(t - tauDes)
            activeCool = activeCool + vars.u_des(k);
        end
    end

    Constraints = [Constraints, vars.n_ads(t) == activeAds];
    Constraints = [Constraints, vars.n_des(t) == activeDes];
    Constraints = [Constraints, vars.n_cool(t) == activeCool];

    if t > tauDes
        Constraints = [Constraints, vars.u_cool(t) == vars.u_des(t - tauDes)];
    else
        Constraints = [Constraints, vars.u_cool(t) == 0];
    end

    Constraints = [Constraints, ...
        vars.n_ready(t) + vars.n_sat(t) + vars.n_ads(t) + vars.n_des(t) + vars.n_cool(t) == vars.Ndac];
    Constraints = [Constraints, vars.u_ads(t) <= vars.n_ready(t)];
    Constraints = [Constraints, vars.u_des(t) <= vars.n_sat(t)];

    Constraints = [Constraints, ...
        vars.P_DAC(t) == params.dac.p_fan_kw_per_unit * vars.n_ads(t) + ...
        params.dac.p_heat_kw_per_unit * vars.n_des(t)];
    Constraints = [Constraints, ...
        vars.m_CO2_prod(t) == params.dac.co2_prod_mol_s_per_unit * vars.n_des(t)];

    completedAds = 0;
    if t > tauAds
        completedAds = vars.u_ads(t - tauAds);
    end

    completedCool = 0;
    if t > (tauDes + tauCool)
        completedCool = vars.u_des(t - tauDes - tauCool);
    end

    if t < T + 1
        Constraints = [Constraints, ...
            vars.n_ready(t + 1) == vars.n_ready(t) - vars.u_ads(t) + completedCool];
        Constraints = [Constraints, ...
            vars.n_sat(t + 1) == vars.n_sat(t) + completedAds - vars.u_des(t)];
    end
end

Constraints = [Constraints, vars.n_ready(T + 1) + vars.n_sat(T + 1) <= vars.Ndac];

aux = struct();
aux.tau_ads = tauAds;
aux.tau_des = tauDes;
aux.tau_cool = tauCool;
aux.co2_prod_mol_s_per_unit = params.dac.co2_prod_mol_s_per_unit;
end
