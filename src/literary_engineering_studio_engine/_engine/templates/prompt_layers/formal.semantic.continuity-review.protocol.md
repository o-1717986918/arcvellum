

这是一份独立复核，不是对模板的确认。核对 delta 的每一项是否有已晋升正文证据、是否重复旧问题、是否给出了合理的未来兑现窗口。

- 审查通过时：`status=complete`、`verdict=pass`、`findings` 非空、`required_changes=[]`。
- 发现问题时：不能伪造 pass；写出可执行的 `required_changes`，等待原作者重新提交 delta。
- `writer_session_id`、`reviewer_session_id` 和 delta 摘要由 Studio 绑定；不要自行创建 completion receipt，也不要编辑正式账本。
