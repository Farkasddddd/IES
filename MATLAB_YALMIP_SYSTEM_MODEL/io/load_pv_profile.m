function pvPowerKw = load_pv_profile(csvPath, pvScale)
%LOAD_PV_PROFILE Load hourly PVWatts AC output and convert to kW.

if ~isfile(csvPath)
    error('PV file not found: %s', csvPath);
end

txt = fileread(csvPath);
lines = regexp(txt, '\r\n|\n|\r', 'split');

headerIdx = [];
for i = 1:numel(lines)
    if contains(lines{i}, 'AC System Output (W)')
        headerIdx = i;
        break;
    end
end

if isempty(headerIdx)
    error('Unable to find the AC System Output header in PV file: %s', csvPath);
end

headerParts = strsplit(lines{headerIdx}, ',');
targetIdx = [];
for j = 1:numel(headerParts)
    token = erase(string(strtrim(headerParts{j})), '"');
    if strcmpi(token, "AC System Output (W)")
        targetIdx = j;
        break;
    end
end

if isempty(targetIdx)
    error('Unable to parse the AC System Output column in PV file: %s', csvPath);
end

numericCol = nan(numel(lines) - headerIdx, 1);
count = 0;

for k = (headerIdx + 1):numel(lines)
    line = strtrim(lines{k});
    if strlength(line) == 0
        continue;
    end

    parts = strsplit(line, ',');
    if numel(parts) < targetIdx
        continue;
    end

    token = erase(string(strtrim(parts{targetIdx})), '"');
    value = str2double(token);
    if ~isnan(value)
        count = count + 1;
        numericCol(count) = value;
    end
end

numericCol = numericCol(1:count);
pvPowerKw = max(0.0, numericCol(:) ./ 1000.0) * pvScale;
end
