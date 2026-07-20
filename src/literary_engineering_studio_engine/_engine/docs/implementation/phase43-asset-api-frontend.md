# Phase 43：API 与前端设定工坊

本阶段为候选资产层新增 FastAPI 和本地前端入口。

## API

- `POST /asset/create`
- `POST /asset/create-character`
- `POST /asset/create-world`
- `POST /asset/create-outline`
- `GET /asset/candidates`
- `POST /asset/review`
- `POST /asset/promote`

`POST /assistant/chat` 也支持“创建角色候选”“创建世界观候选”“创建大纲候选”的基础意图。

## 前端

本地控制台新增“设定工坊”页，可生成、列出、审查和晋升候选资产。
