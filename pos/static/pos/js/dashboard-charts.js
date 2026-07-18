/* CASSEY Dashboard Charts — D3.js v7 */
const chartColors = { teal: '#0d9488', tealLight: '#5eead4', orange: '#f97316', purple: '#8b5cf6', red: '#ef4444', blue: '#3b82f6', pink: '#ec4899', gray: '#94a3b8' };
const colorScale = d3.scaleOrdinal([chartColors.teal, chartColors.orange, chartColors.purple, chartColors.blue, chartColors.pink, chartColors.red, chartColors.gray]);

function initCharts() {
    fetch('/api/dashboard/chart-data/?days=7')
        .then(r => r.json())
        .then(data => {
            drawSalesTrend(data.daily_sales);
            drawPaymentMethods(data.payment_methods);
            drawTopItems(data.top_items);
            drawHourlySales(data.hourly_sales);
            drawCategoryBreakdown(data.categories);
        })
        .catch(e => console.error('Chart data error:', e));
}

function drawSalesTrend(data) {
    const el = document.getElementById('chart-sales-trend');
    el.innerHTML = '';
    const margin = { top: 20, right: 20, bottom: 30, left: 50 };
    const width = el.clientWidth - margin.left - margin.right;
    const height = 200 - margin.top - margin.bottom;

    const svg = d3.select(el).append('svg')
        .attr('width', width + margin.left + margin.right)
        .attr('height', height + margin.top + margin.bottom)
        .append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    const x = d3.scalePoint()
        .domain(data.map(d => d.date.slice(5)))
        .range([0, width]);
    const y = d3.scaleLinear()
        .domain([0, d3.max(data, d => d.total) * 1.1])
        .range([height, 0]);

    svg.append('g').attr('transform', `translate(0,${height})`)
        .call(d3.axisBottom(x).tickValues(x.domain().filter((_, i) => i === 0 || i === data.length - 1 || data.length <= 7)))
        .selectAll('text').attr('fill', '#94a3b8').attr('font-size', '10px');
    svg.append('g').call(d3.axisLeft(y).ticks(4).tickFormat(d => '₱' + (d / 1000).toFixed(1) + 'k'))
        .selectAll('text').attr('fill', '#94a3b8').attr('font-size', '10px');

    const line = d3.line().x(d => x(d.date.slice(5))).y(d => y(d.total)).curve(d3.curveMonotoneX);
    const area = d3.area().x(d => x(d.date.slice(5))).y0(height).y1(d => y(d.total)).curve(d3.curveMonotoneX);

    svg.append('path').datum(data).attr('fill', 'rgba(13,148,136,0.1)').attr('d', area);
    svg.append('path').datum(data).attr('fill', 'none').attr('stroke', chartColors.teal).attr('stroke-width', 2).attr('d', line);

    svg.selectAll('.dot').data(data).enter().append('circle')
        .attr('cx', d => x(d.date.slice(5))).attr('cy', d => y(d.total))
        .attr('r', 3).attr('fill', chartColors.teal).attr('stroke', '#fff').attr('stroke-width', 1.5);
}

function drawPaymentMethods(data) {
    const el = document.getElementById('chart-payment-methods');
    el.innerHTML = '';
    const width = el.clientWidth, height = 200, radius = Math.min(width, height) / 2.5;

    const svg = d3.select(el).append('svg')
        .attr('width', width).attr('height', height)
        .append('g').attr('transform', `translate(${width/2},${height/2})`);

    const pie = d3.pie().value(d => d.total).sort(null);
    const arc = d3.arc().innerRadius(radius * 0.5).outerRadius(radius);
    const labelArc = d3.arc().innerRadius(radius * 0.75).outerRadius(radius * 0.75);

    const paths = svg.selectAll('path').data(pie(data)).enter().append('path')
        .attr('d', arc).attr('fill', (d, i) => colorScale(i))
        .attr('stroke', '#fff').attr('stroke-width', 1.5);

    paths.transition().duration(800).attrTween('d', function(d) {
        const interpolate = d3.interpolate({ startAngle: 0, endAngle: 0 }, d);
        return t => arc(interpolate(t));
    });

    const legend = d3.select(el).append('div').style('display', 'flex').style('flex-wrap', 'wrap').style('gap', '0.5rem').style('padding', '0.5rem');
    data.forEach((d, i) => {
        const names = { CASH: '💵 Cash', GCASH: '📱 GCash', MAYA: '🏦 Maya', CARD: '💳 Card', DIGITAL: '📱 Digital' };
        legend.append('div').style('display', 'flex').style('align-items', 'center').style('gap', '0.3rem').style('font-size', '0.75rem').html(
            `<span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${colorScale(i)}"></span> ${names[d.method] || d.method}`
        );
    });
}

function drawTopItems(data) {
    const el = document.getElementById('chart-top-items');
    el.innerHTML = '';
    const margin = { top: 15, right: 20, bottom: 5, left: 90 };
    const width = el.clientWidth - margin.left - margin.right;
    const height = Math.max(150, data.length * 28) - margin.top - margin.bottom;

    const svg = d3.select(el).append('svg')
        .attr('width', width + margin.left + margin.right)
        .attr('height', height + margin.top + margin.bottom)
        .append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    const x = d3.scaleLinear().domain([0, d3.max(data, d => d.qty) * 1.1]).range([0, width]);
    const y = d3.scaleBand().domain(data.map(d => d.emoji + ' ' + d.name)).range([0, height]).padding(0.25);

    svg.append('g').call(d3.axisLeft(y).tickSize(0)).selectAll('text').attr('font-size', '11px').attr('fill', '#475569');
    svg.append('g').attr('transform', `translate(0,${height})`).call(d3.axisBottom(x).ticks(3)).selectAll('text').attr('fill', '#94a3b8').attr('font-size', '9px');

    svg.selectAll('.bar').data(data).enter().append('rect')
        .attr('y', d => y(d.emoji + ' ' + d.name))
        .attr('height', y.bandwidth())
        .attr('fill', chartColors.teal)
        .attr('rx', 3)
        .transition().duration(600).delay((d, i) => i * 50)
        .attr('width', d => x(d.qty));

    svg.selectAll('.label').data(data).enter().append('text')
        .attr('x', d => x(d.qty) + 5).attr('y', d => y(d.emoji + ' ' + d.name) + y.bandwidth() / 2 + 4)
        .attr('font-size', '10px').attr('fill', '#64748b')
        .text(d => d.qty + ' sold');
}

function drawHourlySales(data) {
    const el = document.getElementById('chart-hourly');
    el.innerHTML = '';
    const margin = { top: 15, right: 10, bottom: 25, left: 40 };
    const width = el.clientWidth - margin.left - margin.right;
    const height = 180 - margin.top - margin.bottom;

    const svg = d3.select(el).append('svg')
        .attr('width', width + margin.left + margin.right)
        .attr('height', height + margin.top + margin.bottom)
        .append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    const x = d3.scaleBand().domain(data.map(d => d.hour)).range([0, width]).padding(0.15);
    const y = d3.scaleLinear().domain([0, d3.max(data, d => d.total) * 1.1]).range([height, 0]);

    svg.append('g').attr('transform', `translate(0,${height})`)
        .call(d3.axisBottom(x).tickFormat(d => d + ':00').tickValues(x.domain().filter((_, i) => i % 2 === 0)))
        .selectAll('text').attr('fill', '#94a3b8').attr('font-size', '9px').attr('transform', 'rotate(-30)');

    svg.selectAll('.bar').data(data).enter().append('rect')
        .attr('x', d => x(d.hour)).attr('y', d => y(d.total))
        .attr('width', x.bandwidth()).attr('height', d => height - y(d.total))
        .attr('fill', d => d.total > 0 ? chartColors.teal : '#e2e8f0').attr('rx', 2)
        .transition().duration(400).delay((d, i) => i * 30);
}

function drawCategoryBreakdown(data) {
    const el = document.getElementById('chart-categories');
    el.innerHTML = '';
    if (data.length === 0) { el.innerHTML = '<div style="padding:2rem;text-align:center;color:#94a3b8;font-size:0.85rem;">No data yet</div>'; return; }
    const total = d3.sum(data, d => d.total);
    const margin = { top: 15, right: 10, bottom: 5, left: 100 };
    const width = el.clientWidth - margin.left - margin.right;
    const height = Math.max(100, data.length * 24) - margin.top - margin.bottom;

    const svg = d3.select(el).append('svg')
        .attr('width', width + margin.left + margin.right)
        .attr('height', height + margin.top + margin.bottom)
        .append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    const x = d3.scaleLinear().domain([0, 100]).range([0, width]);
    const y = d3.scaleBand().domain(data.map(d => d.name)).range([0, height]).padding(0.2);

    svg.append('g').call(d3.axisLeft(y).tickSize(0)).selectAll('text').attr('font-size', '10px').attr('fill', '#475569');

    svg.selectAll('.bar').data(data).enter().append('rect')
        .attr('y', d => y(d.name)).attr('height', y.bandwidth())
        .attr('fill', (d, i) => colorScale(i)).attr('rx', 3)
        .transition().duration(600).delay((d, i) => i * 40)
        .attr('width', d => x(d.total / total * 100));

    svg.selectAll('.pct').data(data).enter().append('text')
        .attr('x', d => x(d.total / total * 100) + 5)
        .attr('y', d => y(d.name) + y.bandwidth() / 2 + 4)
        .attr('font-size', '10px').attr('fill', '#64748b')
        .text(d => '₱' + d.total.toFixed(0) + ' (' + (d.total / total * 100).toFixed(1) + '%)');
}
