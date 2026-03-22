function scenarios = load_codex_market_scenarios(pyFilePath)
%LOAD_CODEX_MARKET_SCENARIOS Parse methanol price scenarios from existing Python config.

if ~isfile(pyFilePath)
    error('Market scenario file not found: %s', pyFilePath);
end

txt = fileread(pyFilePath);
pattern = [
    '(?<var>[A-Z_]+)\s*=\s*MethanolPriceScenario\(\s*' ...
    'name\s*=\s*"(?<name>[^"]+)"\s*,\s*' ...
    'methanol_price_yuan_per_kg\s*=\s*(?<price>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)'
    ];
matches = regexp(txt, pattern, 'names');

scenarios = struct();
for i = 1:numel(matches)
    key = matlab.lang.makeValidName(lower(matches(i).name));
    scenarios.(key) = struct( ...
        'python_symbol', matches(i).var, ...
        'name', matches(i).name, ...
        'methanol_price_yuan_per_kg', str2double(matches(i).price));
end

if isfield(scenarios, 'green_base')
    scenarios.default = scenarios.green_base;
elseif ~isempty(fieldnames(scenarios))
    names = fieldnames(scenarios);
    scenarios.default = scenarios.(names{1});
else
    scenarios.default = struct('name', 'fallback', 'methanol_price_yuan_per_kg', 6.0);
end
end
