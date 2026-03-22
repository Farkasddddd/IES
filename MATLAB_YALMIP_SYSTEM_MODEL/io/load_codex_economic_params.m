function econ = load_codex_economic_params(pyFilePath)
%LOAD_CODEX_ECONOMIC_PARAMS Parse economic defaults from the existing Python config.

if ~isfile(pyFilePath)
    error('Economic parameter file not found: %s', pyFilePath);
end

txt = fileread(pyFilePath);

econ = struct();
econ.pv_cost_per_kw = extract_scalar(txt, 'pv_cost_per_kw', 2700.0);
econ.dac_cost_per_unit = extract_scalar(txt, 'dac_cost_per_unit', 8000.0);
econ.pem_cost_per_kw = extract_scalar(txt, 'pem_cost_per_kw', 5000.0);
econ.battery_cost_per_kwh = extract_scalar(txt, 'battery_cost_per_kwh', 1500.0);
econ.co2_tank_cost_per_mol = extract_scalar(txt, 'co2_tank_cost_per_mol', 0.1);
econ.h2_tank_cost_per_mol = extract_scalar(txt, 'h2_tank_cost_per_mol', 8.0);
econ.discount_rate = extract_scalar(txt, 'discount_rate', 0.05);
econ.project_lifetime_years = extract_scalar(txt, 'project_lifetime_years', 20);
econ.grid_purchase_price_per_kwh = extract_scalar(txt, 'grid_purchase_price_per_kwh', 0.65);

r = econ.discount_rate;
n = econ.project_lifetime_years;
econ.crf = (r * (1 + r)^n) / ((1 + r)^n - 1);
econ.source_file = pyFilePath;
end

function value = extract_scalar(txt, fieldName, fallbackValue)
pattern = [fieldName, '\s*:\s*[A-Za-z0-9_]+\s*=\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)'];
token = regexp(txt, pattern, 'tokens', 'once');

if isempty(token)
    value = fallbackValue;
else
    value = str2double(token{1});
end
end
