const courses = [
  {name: "Python 入门", hours: 18, path: "/courses/python-intro", tags: "Python 编程 初级"},
  {name: "Playwright 自动化", hours: 12, path: "/courses/playwright", tags: "测试 浏览器 中级"},
  {name: "React 实战", hours: 24, path: "/courses/react-practice", tags: "前端 React 中级"},
  {name: "数据分析基础", hours: 16, path: "/courses/data-analysis", tags: "Python 数据 初级"},
  {name: "Agent 工程实践", hours: 20, path: "/courses/agent-engineering", tags: "AI Agent 高级"},
  {name: "SQL 入门", hours: 10, path: "/courses/sql-intro", tags: "SQL 数据库 初级"}
];
const list = document.querySelector("#course-list"), count = document.querySelector("#course-count"), query = document.querySelector("#course-query"), select = document.querySelector("#signup-course");
function render(items) {
  list.innerHTML = items.map(course => `<article class="course-card"><p class="eyebrow">${course.tags}</p><h3>${course.name}</h3><p><strong>${course.hours} 小时</strong></p><p class="path">${course.path}</p><button type="button" data-course-path="${course.path}">查看 ${course.name}详情</button></article>`).join("") || '<p class="empty">没有匹配的课程</p>';
  count.textContent = `${items.length} 门课程`;
  list.querySelectorAll('[data-course-path]').forEach(button => button.addEventListener('click', () => {
    const course = courses.find(item => item.path === button.dataset.coursePath);
    const detail = document.querySelector('#course-detail');
    detail.hidden = false;
    detail.innerHTML = `<p class="eyebrow">COURSE DETAIL</p><h3>课程详情</h3><p>课程：${course.name}</p><p>时长：${course.hours} 小时</p><p>链接：${course.path}</p>`;
  }));
}
courses.forEach(course => select.add(new Option(course.name, course.name))); render(courses);
document.querySelector("#search-button").addEventListener("click", () => { const keyword = query.value.trim().toLowerCase(); render(courses.filter(course => `${course.name} ${course.tags}`.toLowerCase().includes(keyword))); });
document.querySelector("#reset-button").addEventListener("click", () => { query.value = ""; render(courses); });
document.querySelector("#signup-form").addEventListener("submit", event => {
  event.preventDefault(); const name = document.querySelector("#signup-name").value.trim(), email = document.querySelector("#signup-email").value.trim(), course = select.value, receipt = document.querySelector("#receipt");
  receipt.hidden = false; receipt.textContent = `提交成功｜姓名：${name}｜邮箱：${email}｜课程：${course}`;
});
