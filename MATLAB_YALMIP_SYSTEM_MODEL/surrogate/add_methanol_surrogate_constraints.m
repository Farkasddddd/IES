function Constraints = add_methanol_surrogate_constraints(Constraints, vars, lookup, params)
%ADD_METHANOL_SURROGATE_CONSTRAINTS Fixed-ratio lookup approximation.

T = length(vars.F_CO2);
positiveFeeds = lookup.feed_breakpoints(lookup.feed_breakpoints > 0);

if isempty(params.surrogate.min_feed_co2_mol_s)
    if isempty(positiveFeeds)
        error('Methanol lookup does not contain any positive feed breakpoint.');
    end
    minFeed = min(positiveFeeds);
else
    minFeed = params.surrogate.min_feed_co2_mol_s;
end

if isfield(params.surrogate, 'max_feed_co2_mol_s') && ~isempty(params.surrogate.max_feed_co2_mol_s)
    maxFeed = min(lookup.feed_max, params.surrogate.max_feed_co2_mol_s);
else
    maxFeed = lookup.feed_max;
end

Constraints = [Constraints, vars.F_CO2 >= 0, vars.F_H2 >= 0];
Constraints = [Constraints, vars.M >= 0, vars.P_MeOH >= 0];
Constraints = [Constraints, vars.F_CO2 <= maxFeed];
Constraints = [Constraints, vars.z_MeOH_on >= 0, vars.z_MeOH_on <= 1];

if isfield(params.surrogate, 'enforce_startup_then_continuous') && ...
        params.surrogate.enforce_startup_then_continuous
    for t = 1:(T - 1)
        Constraints = [Constraints, vars.z_MeOH_on(t + 1) >= vars.z_MeOH_on(t)];
    end
elseif isfield(params.surrogate, 'always_on') && params.surrogate.always_on
    Constraints = [Constraints, vars.z_MeOH_on == 1];
end

if isfield(params.surrogate, 'min_on_hours') && params.surrogate.min_on_hours > 0
    Constraints = [Constraints, sum(vars.z_MeOH_on) >= params.surrogate.min_on_hours];
end

Constraints = [Constraints, vars.F_CO2 <= maxFeed * vars.z_MeOH_on];

if params.surrogate.enforce_continuous_operation
    Constraints = [Constraints, vars.F_CO2 >= minFeed * vars.z_MeOH_on];
end

for t = 1:T
    Constraints = [Constraints, vars.F_H2(t) == lookup.fixed_ratio * vars.F_CO2(t)];
    Constraints = [Constraints, ...
        vars.M(t) == interp1( ...
        lookup.feed_breakpoints, ...
        lookup.methanol_breakpoints, ...
        vars.F_CO2(t), ...
        'sos2')];
    Constraints = [Constraints, ...
        vars.P_MeOH(t) == interp1( ...
        lookup.feed_breakpoints, ...
        lookup.power_breakpoints, ...
        vars.F_CO2(t), ...
        'sos2')];
end
end
