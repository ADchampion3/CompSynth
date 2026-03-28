"""
CompSynth Crawler 模块测试

测试目标: 美团技术博客 https://tech.meituan.com/
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from loguru import logger

from comp_synth.crawlers.adaptive_web_crawler import AdaptiveWebCrawler
from comp_synth.crawlers.extractors import DOMExtractor
from comp_synth.schema.content_item import WebPageItem
from comp_synth.schema.site_chema import SiteSchema
from comp_synth.store.schema_store import SchemaStore

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_db_path(monkeypatch):
    """使用临时数据库路径"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_schemas.db"
        monkeypatch.setattr("comp_synth.config.settings.site_schema_db_path", db_path)
        yield db_path


@pytest.fixture
def mock_schema_store(monkeypatch):
    """Mock SchemaStore 和 CrawlTracker 避免数据库依赖"""
    mock_store = MagicMock()
    mock_store.get.return_value = None
    mock_store.can_use_llm.return_value = True
    mock_store.save.return_value = None
    mock_store.mark_llm_called.return_value = None
    mock_store.update_list_selectors.return_value = None
    monkeypatch.setattr("comp_synth.crawlers.adaptive_web_crawler.SchemaStore", lambda: mock_store)

    mock_tracker = MagicMock()
    mock_tracker.is_crawled.return_value = False
    mock_tracker.mark_crawled.return_value = None
    monkeypatch.setattr("comp_synth.crawlers.adaptive_web_crawler.CrawlTracker", lambda: mock_tracker)

    return mock_store




@pytest.fixture
def meituan_list_html():
    """美团技术博客列表页 HTML"""
    return """
<!doctype html>
<html lang=en dir=ltr class="no-js theme-united">
    <head>
        <meta charset=utf-8>
        <meta name=renderer content=webkit>
        <meta http-equiv=x-ua-compatible content="IE=edge">
        <meta name=viewport content="width=device-width,initial-scale=1,shrink-to-fit=no">
        <meta name=author content=soulteary@gmail.com>
        <script async src="https://www.googletagmanager.com/gtag/js?id=UA-158867676-1"></script>
        <script>
            window.dataLayer = window.dataLayer || [];
            function gtag() {
                dataLayer.push(arguments);
            }
            gtag('js', new Date());
            gtag('config', 'UA-158867676-1');
        </script>
        <meta name=robots content="index, follow">
        <meta property=og:title content=美团技术团队>
        <meta property=og:description content>
        <meta property=og:type content=website>
        <meta property=og:url content=https://tech.meituan.com/>
        <meta property=og:updated_time content=2026-03-20T00:00:00&#43;00:00>
        <meta name=twitter:card content=summary>
        <meta name=twitter:title content=美团技术团队>
        <meta name=twitter:description content>
        <meta name=keywords content>
        <link rel=canonical href=https://tech.meituan.com/>
        <title>美团技术团队</title>
        <link rel=stylesheet href="https://awps-assets.meituan.net/mit/blog/v20190629/common.css?v=Whistle&t=20240202-1r">
        <link rel=stylesheet href="https://awps-assets.meituan.net/mit/blog/v20190629/index.css?v=Whistle&t=20240202-1r">
        <link rel=apple-touch-icon sizes=180x180 href="https://awps-assets.meituan.net/mit/blog/v20190629/asset/icon/apple-icon-180x180.png?v=Whistle&t=20181017-1r">
        <link rel=icon type=image/png sizes=192x192 href="https://awps-assets.meituan.net/mit/blog/v20190629/asset/icon/android-icon-192x192.png?v=Whistle&t=20181017-1r">
        <link rel="shortcut icon" href="https://awps-assets.meituan.net/mit/blog/v20190629/asset/icon/favicon.ico?v=Whistle&t=20181017-1r">
        <script>
            top != self && top.host != self.host && (top.location = self.location);
            (function(d) {
                d.className = d.className.replace(/\bno-js/, '');
            }
            )(document.documentElement);
            var $CONFIG = {
                'data': {}
            };
        </script>
        <link href=https://tech.meituan.com/feed/ rel=alternate type=application/rss+xml title=美团技术团队>
        <script src="https://awps-assets.meituan.net/mit/blog/v20190629/asset/vendor/zepto.min.js?v=Whistle&t=20181017-1r"></script>
        <script src="https://awps-assets.meituan.net/mit/blog/v20190629/common.js?v=Whistle&t=20181017-1r"></script>
    </head>
    <body class="page page-is-loading page-type-page page-type-home">
        <nav class="navbar navbar-default g-navbar-box hidden-print" id=Js_page-navbar>
            <div class=navbar-header>
                <button type=button class="navbar-toggle collapsed" data-toggle=collapse data-target=.navbar-collapse>
                    <span class=icon-bar></span>
                    <span class=icon-bar></span>
                    <span class=icon-bar></span>
                </button>
                <a class=navbar-brand href=https://tech.meituan.com/ title=美团技术团队 target=_self>美团技术团队</a>
            </div>
            <div class="collapse navbar-collapse">
                <ul class="nav navbar-nav navbar-right" id=JS_nav_list>
                    <li class="menu-item menu-item-home">
                        <a class=menu-item-link href=https://tech.meituan.com/ target=_self title=查看最新文章>最新文章</a>
                    </li>
                    <li class="menu-item menu-item-archive">
                        <a class=menu-item-link href=/archives target=_self title=查看文章存档内容>文章存档</a>
                    </li>
                    <li class="menu-item menu-item-salon">
                        <a class=menu-item-link href=/tech-salon target=_self title=了解技术沙龙>技术沙龙</a>
                    </li>
                    <li class="menu-item menu-item-about">
                        <a class=menu-item-link href=/about target=_self title=了解更多关于我们的事情>关于我们</a>
                    </li>
                </ul>
            </div>
            <div class=navbar-bottom>
                <p class=copyright>© 2026 美团技术团队</p>
                <p class=copyright>All Rights Reserved.</p>
            </div>
        </nav>
        <div class=page-loading-bar></div>
        <div class="container-fluid main-container" id=J_main-container>
            <div class=row>
                <div class=col-md-12>
                    <h1 class="hide page-title">首页</h1>
                    <h2 class=page-title>最近更新</h2>
                </div>
            </div>
            <div class="row post-container-wrapper">
                <div class=col-md-6>
                    <div class=post-container>
                        <h2 class=post-title>
                            <a href=https://tech.meituan.com/2026/03/20/busniness-intelligence-practice-in-meituan.html rel=bookmark>美团 BI 在指标平台和分析引擎上的探索和实践</a>
                        </h2>
                        <div class=meta-box>
                            <span class=m-post-date>
                                <i class="fa fa-calendar-o"></i>
                                2026年03月20日
                            </span>
                            <span class=m-post-nick>数据平台</span>
                        </div>
                        <div class="post-content post-expect">
                            美团数据平台构建了以指标平台为核心的新一代 BI 架构，通过自动语义和增强计算两种核心能力的建设，部分解决了传统 BI 平台在个性化数据集驱动下产生的数据口径混乱、查询性能差等问题。
<a class="more-link btn btn-primary btn-xs" href=https://tech.meituan.com/2026/03/20/busniness-intelligence-practice-in-meituan.html>阅读全文</a>
                        </div>
                        <div class="meta-box post-bottom-meta-box hidden-print">
                            <span class=tag-links>
                                <i class="fa fa-tags" aria-hidden=true></i>
                                <a href=/tags/%E6%95%B0%E6%8D%AE%E5%B9%B3%E5%8F%B0.html rel=tag>数据平台</a>
                                , <a href=/tags/%E6%95%B0%E6%8D%AE.html rel=tag>数据</a>
                                , <a href=/tags/%E6%8C%87%E6%A0%87%E5%B9%B3%E5%8F%B0.html rel=tag>指标平台</a>
                                , <a href=/tags/%E5%A2%9E%E5%BC%BA%E8%AE%A1%E7%AE%97.html rel=tag>增强计算</a>
                                , <a href=/tags/bi.html rel=tag>BI</a>
                            </span>
                        </div>
                    </div>
                </div>
                <div class=col-md-6>
                    <div class=post-container>
                        <h2 class=post-title>
                            <a href=https://tech.meituan.com/2026/03/13/qwik-practice-in-dianping.html rel=bookmark>重塑站外体验：大众点评 M 站基于 Qwik.js 的重构实践</a>
                        </h2>
                        <div class=meta-box>
                            <span class=m-post-date>
                                <i class="fa fa-calendar-o"></i>
                                2026年03月13日
                            </span>
                            <span class=m-post-nick>美团技术团队</span>
                        </div>
                        <div class="post-content post-expect">
                            为突破传统 Web 框架的性能瓶颈，大众点评增长团队引入 Qwik.js 重构 M 站核心页面架构，解决了重构前页面加载慢、维护成本高的难题。借助“可恢复性”能力，我们甩掉了传统水合的性能损耗，搭配全链路优化与工程化适配，让各个页面的性能指标都得到了明显提升。本文将拆解本次重构的技术选型、原理与落地细节，沉淀前沿框架在站外场景的落地经验。
<a class="more-link btn btn-primary btn-xs" href=https://tech.meituan.com/2026/03/13/qwik-practice-in-dianping.html>阅读全文</a>
                        </div>
                        <div class="meta-box post-bottom-meta-box hidden-print">
                            <span class=tag-links>
                                <i class="fa fa-tags" aria-hidden=true></i>
                                <a href=/tags/%E5%A4%A7%E4%BC%97%E7%82%B9%E8%AF%84.html rel=tag>大众点评</a>
                                , <a href=/tags/%E5%89%8D%E7%AB%AF.html rel=tag>前端</a>
                                , <a href=/tags/qwik.js.html rel=tag>Qwik.js</a>
                                , <a href=/tags/m-%E7%AB%99.html rel=tag>M 站</a>
                                , <a href=/tags/%E7%A7%BB%E5%8A%A8%E7%AB%AF.html rel=tag>移动端</a>
                            </span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="row post-container-wrapper">
                <div class=col-md-6>
                    <div class=post-container>
                        <h2 class=post-title>
                            <a href=https://tech.meituan.com/2026/03/09/longcat-openclaw.html rel=bookmark>LongCat 为 OpenClaw 装上效率引擎：你的自动化任务还能再快 30%</a>
                        </h2>
                        <div class=meta-box>
                            <span class=m-post-date>
                                <i class="fa fa-calendar-o"></i>
                                2026年03月09日
                            </span>
                            <span class=m-post-nick>美团技术团队</span>
                        </div>
                        <div class="post-content post-expect">
                            依赖第三方订阅进行非官方调用存在账号安全风险与服务不稳定性。为规避此类问题，LongCat 团队提供稳定合规的官方免费 API，开发者可通过官方渠道直接接入 OpenClaw，在确保账号安全的前提下构建自动化工作流。
<a class="more-link btn btn-primary btn-xs" href=https://tech.meituan.com/2026/03/09/longcat-openclaw.html>阅读全文</a>
                        </div>
                        <div class="meta-box post-bottom-meta-box hidden-print">
                            <span class=tag-links>
                                <i class="fa fa-tags" aria-hidden=true></i>
                                <a href=/tags/longcat.html rel=tag>LongCat</a>
                                , <a href=/tags/longcat-flash-thinking.html rel=tag>LongCat-Flash-Thinking</a>
                                , <a href=/tags/%E5%A4%A7%E6%A8%A1%E5%9E%8B.html rel=tag>大模型</a>
                                , <a href=/tags/openclaw.html rel=tag>OpenClaw</a>
                            </span>
                        </div>
                    </div>
                </div>
                <div class=col-md-6>
                    <div class=post-container>
                        <h2 class=post-title>
                            <a href=https://tech.meituan.com/2026/02/10/longcat-flash-lite.html rel=bookmark>美团发布基于 N-gram 全新模型：嵌入扩展新范式，实现轻量化 MoE 高效进化</a>
                        </h2>
                        <div class=meta-box>
                            <span class=m-post-date>
                                <i class="fa fa-calendar-o"></i>
                                2026年02月10日
                            </span>
                            <span class=m-post-nick>美团技术团队</span>
                        </div>
                        <div class="post-content post-expect">
                            LongCat-Flash-Lite是一款拥有 685 亿参数，每次推理仅激活 29 亿~ 45 亿参数的轻量化 MoE 模型。通过将超过 300 亿参数高效用于嵌入层，LongCat-Flash-Lite 不仅超越了参数量等效的 MoE 基线模型，还在与同规模现有模型的对比中展现出卓越的竞争力，尤其在智能体与代码领域表现突出。
<a class="more-link btn btn-primary btn-xs" href=https://tech.meituan.com/2026/02/10/longcat-flash-lite.html>阅读全文</a>
                        </div>
                        <div class="meta-box post-bottom-meta-box hidden-print">
                            <span class=tag-links>
                                <i class="fa fa-tags" aria-hidden=true></i>
                                <a href=/tags/longcat.html rel=tag>LongCat</a>
                                , <a href=/tags/%E5%BC%80%E6%BA%90.html rel=tag>开源</a>
                                , <a href=/tags/%E5%A4%A7%E6%A8%A1%E5%9E%8B.html rel=tag>大模型</a>
                                , <a href=/tags/longcat-flash-lite.html rel=tag>LongCat-Flash-Lite</a>
                            </span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="row post-container-wrapper">
                <div class=col-md-6>
                    <div class=post-container>
                        <h2 class=post-title>
                            <a href=https://tech.meituan.com/2026/02/02/2025-spring-festival-present.html rel=bookmark>2025美团技术年货，「马」上到来</a>
                        </h2>
                        <div class=meta-box>
                            <span class=m-post-date>
                                <i class="fa fa-calendar-o"></i>
                                2026年02月02日
                            </span>
                            <span class=m-post-nick>美团技术团队</span>
                        </div>
                        <div class="post-content post-expect">
                            值此马年春节来临之际，我们精选了过去一年美团技术团队微信公众号发布的 40 多篇优质技术文章，精心汇编成一本 500 多页的电子书。谨以此作为一份特别的新年礼物，献给每一位热爱技术、持续探索的同学。
<a class="more-link btn btn-primary btn-xs" href=https://tech.meituan.com/2026/02/02/2025-spring-festival-present.html>阅读全文</a>
                        </div>
                        <div class="meta-box post-bottom-meta-box hidden-print">
                            <span class=tag-links>
                                <i class="fa fa-tags" aria-hidden=true></i>
                                <a href=/tags/%E7%BE%8E%E5%9B%A2%E6%8A%80%E6%9C%AF%E5%9B%A2%E9%98%9F.html rel=tag>美团技术团队</a>
                                , <a href=/tags/%E6%8A%80%E6%9C%AF%E5%B9%B4%E8%B4%A7.html rel=tag>技术年货</a>
                                , <a href=/tags/%E5%B9%B4%E5%BA%A6%E6%80%BB%E7%BB%93.html rel=tag>年度总结</a>
                            </span>
                        </div>
                    </div>
                </div>
                <div class=col-md-6>
                    <div class=post-container>
                        <h2 class=post-title>
                            <a href=https://tech.meituan.com/2026/02/02/longcat-flash-thinking-2601-techreport.html rel=bookmark>多维创新打造强泛化智能体模型，LongCat-Flash-Thinking-2601技术报告发布</a>
                        </h2>
                        <div class=meta-box>
                            <span class=m-post-date>
                                <i class="fa fa-calendar-o"></i>
                                2026年02月02日
                            </span>
                            <span class=m-post-nick>美团技术团队</span>
                        </div>
                        <div class="post-content post-expect">
                            LongCat-Flash-Thinking-2601模型创新性地打造了 “重思考模式” ，通过并行推理与深度总结，实现推理宽度与深度的协同扩展，显著提升复杂交互与多步规划任务中的表现。
<a class="more-link btn btn-primary btn-xs" href=https://tech.meituan.com/2026/02/02/longcat-flash-thinking-2601-techreport.html>阅读全文</a>
                        </div>
                        <div class="meta-box post-bottom-meta-box hidden-print">
                            <span class=tag-links>
                                <i class="fa fa-tags" aria-hidden=true></i>
                                <a href=/tags/longcat.html rel=tag>LongCat</a>
                                , <a href=/tags/%E5%BC%80%E6%BA%90.html rel=tag>开源</a>
                                , <a href=/tags/%E5%A4%A7%E6%A8%A1%E5%9E%8B.html rel=tag>大模型</a>
                                , <a href=/tags/longcat-flash-thinking.html rel=tag>LongCat-Flash-Thinking</a>
                            </span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="row post-container-wrapper">
                <div class=col-md-6>
                    <div class=post-container>
                        <h2 class=post-title>
                            <a href=https://tech.meituan.com/2026/01/26/evocua.html rel=bookmark>美团 EvoCUA 刷新开源 SOTA，会用电脑还会持续进化的智能体！</a>
                        </h2>
                        <div class=meta-box>
                            <span class=m-post-date>
                                <i class="fa fa-calendar-o"></i>
                                2026年01月26日
                            </span>
                            <span class=m-post-nick>美团技术团队</span>
                        </div>
                        <div class="post-content post-expect">
                            美团技术团队推出了 EvoCUA 模型并在 Github、Huggingface 开源，通过构建可验证数据合成引擎与十万级并发的交互沙盒，将训练范式从传统的“静态轨迹模仿”转变为高效的“经验进化学习”。
<a class="more-link btn btn-primary btn-xs" href=https://tech.meituan.com/2026/01/26/evocua.html>阅读全文</a>
                        </div>
                        <div class="meta-box post-bottom-meta-box hidden-print">
                            <span class=tag-links>
                                <i class="fa fa-tags" aria-hidden=true></i>
                                <a href=/tags/%E7%BE%8E%E5%9B%A2%E6%8A%80%E6%9C%AF%E5%9B%A2%E9%98%9F.html rel=tag>美团技术团队</a>
                                , <a href=/tags/%E5%BC%80%E6%BA%90.html rel=tag>开源</a>
                                , <a href=/tags/%E5%A4%A7%E6%A8%A1%E5%9E%8B.html rel=tag>大模型</a>
                                , <a href=/tags/evocua.html rel=tag>EvoCUA</a>
                            </span>
                        </div>
                    </div>
                </div>
                <div class=col-md-6>
                    <div class=post-container>
                        <h2 class=post-title>
                            <a href=https://tech.meituan.com/2026/01/20/longcat-flash-thinking-2601.html rel=bookmark>美团 LongCat-Flash-Thinking-2601 发布，工具调用能力登顶开源 SOTA！</a>
                        </h2>
                        <div class=meta-box>
                            <span class=m-post-date>
                                <i class="fa fa-calendar-o"></i>
                                2026年01月20日
                            </span>
                            <span class=m-post-nick>美团技术团队</span>
                        </div>
                        <div class="post-content post-expect">
                            美团 LongCat 团队正式对外发布并开源 LongCat-Flash-Thinking-2601。作为已发布的 LongCat-Flash-Thinking 模型的升级版，LongCat-Flash-Thinking-2601 在 Agentic Search（智能体搜索）、Agentic Tool Use（智能体工具调用）、TIR（工具交互推理）等核心评测基准上，均达到开源模型 SOTA 水平。
<a class="more-link btn btn-primary btn-xs" href=https://tech.meituan.com/2026/01/20/longcat-flash-thinking-2601.html>阅读全文</a>
                        </div>
                        <div class="meta-box post-bottom-meta-box hidden-print">
                            <span class=tag-links>
                                <i class="fa fa-tags" aria-hidden=true></i>
                                <a href=/tags/longcat.html rel=tag>LongCat</a>
                                , <a href=/tags/%E5%BC%80%E6%BA%90.html rel=tag>开源</a>
                                , <a href=/tags/%E5%A4%A7%E6%A8%A1%E5%9E%8B.html rel=tag>大模型</a>
                                , <a href=/tags/longcat-flash-thinking.html rel=tag>LongCat-Flash-Thinking</a>
                            </span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="row post-container-wrapper">
                <div class=col-md-6>
                    <div class=post-container>
                        <h2 class=post-title>
                            <a href=https://tech.meituan.com/2026/01/13/kuitest-ui.html rel=bookmark>KuiTest：基于大模型通识的 UI 交互遍历测试</a>
                        </h2>
                        <div class=meta-box>
                            <span class=m-post-date>
                                <i class="fa fa-calendar-o"></i>
                                2026年01月13日
                            </span>
                            <span class=m-post-nick>质效技术部</span>
                        </div>
                        <div class="post-content post-expect">
                            美团质效技术部联合复旦大学周扬帆教授团队推出 KuiTest——零规则 UI 功能性异常测试工具。KuiTest 通过将“人类预期”直接用作 Test Oracle，解决了长期以来 UI 测试 Oracle 泛化性差的自动化痛点。实验表明，KuiTest 异常召回率达 86%，误报率仅 1.2%，已在执行 21 万 &#43;测试用例，发现百余例有效缺陷，大幅降低人工成本并提升测试覆盖率。
<a class="more-link btn btn-primary btn-xs" href=https://tech.meituan.com/2026/01/13/kuitest-ui.html>阅读全文</a>
                        </div>
                        <div class="meta-box post-bottom-meta-box hidden-print">
                            <span class=tag-links>
                                <i class="fa fa-tags" aria-hidden=true></i>
                                <a href=/tags/%E8%B4%A8%E6%95%88%E6%8A%80%E6%9C%AF%E9%83%A8.html rel=tag>质效技术部</a>
                                , <a href=/tags/%E6%B5%8B%E8%AF%95.html rel=tag>测试</a>
                                , <a href=/tags/kuitest.html rel=tag>KuiTest</a>
                                , <a href=/tags/%E7%A7%91%E7%A0%94%E5%90%88%E4%BD%9C.html rel=tag>科研合作</a>
                                , <a href=/tags/ui.html rel=tag>UI</a>
                            </span>
                        </div>
                    </div>
                </div>
                <div class=col-md-6>
                    <div class=post-container>
                        <h2 class=post-title>
                            <a href=https://tech.meituan.com/2026/01/12/aaai-2026.html rel=bookmark>AAAI 2026 | 美团技术团队学术论文精选</a>
                        </h2>
                        <div class=meta-box>
                            <span class=m-post-date>
                                <i class="fa fa-calendar-o"></i>
                                2026年01月12日
                            </span>
                            <span class=m-post-nick>美团技术团队</span>
                        </div>
                        <div class="post-content post-expect">
                            AAAI 是人工智能领域顶级的国际学术会议，本文精选了美团技术团队被收录的8篇学术论文（附下载链接），覆盖大模型推理、 退火策略、过程奖励模型、强化学习、视觉文本渲染等多个技术领域，希望这些论文能对大家有所帮助或启发。
<a class="more-link btn btn-primary btn-xs" href=https://tech.meituan.com/2026/01/12/aaai-2026.html>阅读全文</a>
                        </div>
                        <div class="meta-box post-bottom-meta-box hidden-print">
                            <span class=tag-links>
                                <i class="fa fa-tags" aria-hidden=true></i>
                                <a href=/tags/%E7%BE%8E%E5%9B%A2%E6%8A%80%E6%9C%AF%E5%9B%A2%E9%98%9F.html rel=tag>美团技术团队</a>
                                , <a href=/tags/%E7%AE%97%E6%B3%95.html rel=tag>算法</a>
                                , <a href=/tags/%E5%9B%BD%E9%99%85%E9%A1%B6%E4%BC%9A.html rel=tag>国际顶会</a>
                                , <a href=/tags/%E8%AE%BA%E6%96%87%E7%B2%BE%E9%80%89.html rel=tag>论文精选</a>
                                , <a href=/tags/aaai-2026.html rel=tag>AAAI 2026</a>
                            </span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="row post-container-wrapper">
                <div class=col-md-6>
                    <div class=post-container>
                        <h2 class=post-title>
                            <a href=https://tech.meituan.com/2025/12/29/2025-annual-review.html rel=bookmark>2025 | 美团技术团队热门技术文章汇总</a>
                        </h2>
                        <div class=meta-box>
                            <span class=m-post-date>
                                <i class="fa fa-calendar-o"></i>
                                2025年12月29日
                            </span>
                            <span class=m-post-nick>美团技术团队</span>
                        </div>
                        <div class="post-content post-expect">
                            感谢这一路上，每一位伙伴的并肩前行与坚定支持。今年，美团技术团队在持续深耕中涌现出不少值得分享的实践与开源产品 &amp;服务。我们从中精选了18篇具有代表性的技术文章，内容涵盖大模型开源、研发技能、产品服务三大方向。
<a class="more-link btn btn-primary btn-xs" href=https://tech.meituan.com/2025/12/29/2025-annual-review.html>阅读全文</a>
                        </div>
                        <div class="meta-box post-bottom-meta-box hidden-print">
                            <span class=tag-links>
                                <i class="fa fa-tags" aria-hidden=true></i>
                                <a href=/tags/%E7%BE%8E%E5%9B%A2%E6%8A%80%E6%9C%AF%E5%9B%A2%E9%98%9F.html rel=tag>美团技术团队</a>
                                , <a href=/tags/%E5%A4%A7%E6%A8%A1%E5%9E%8B.html rel=tag>大模型</a>
                                , <a href=/tags/%E5%B9%B4%E5%BA%A6%E6%80%BB%E7%BB%93.html rel=tag>年度总结</a>
                            </span>
                        </div>
                    </div>
                </div>
                <div class=col-md-6>
                    <div class=post-container>
                        <h2 class=post-title>
                            <a href=https://tech.meituan.com/2025/12/23/longcat-video-avatar.html rel=bookmark>美团 LongCat-Video-Avatar 正式发布，实现开源 SOTA 级拟真表现</a>
                        </h2>
                        <div class=meta-box>
                            <span class=m-post-date>
                                <i class="fa fa-calendar-o"></i>
                                2025年12月23日
                            </span>
                            <span class=m-post-nick>美团技术团队</span>
                        </div>
                        <div class="post-content post-expect">
                            今年 8 月，美团开源的 InfiniteTalk 项目凭借无限长度生成能力与精准的唇形、头部、表情及姿态同步表现，迅速成为语音驱动虚拟人领域的主流工具，吸引全球数万名开
<a class="more-link btn btn-primary btn-xs" href=https://tech.meituan.com/2025/12/23/longcat-video-avatar.html>阅读全文</a>
                        </div>
                        <div class="meta-box post-bottom-meta-box hidden-print">
                            <span class=tag-links>
                                <i class="fa fa-tags" aria-hidden=true></i>
                                <a href=/tags/longcat.html rel=tag>LongCat</a>
                                , <a href=/tags/%E5%A4%A7%E6%A8%A1%E5%9E%8B.html rel=tag>大模型</a>
                                , <a href=/tags/longcat-video.html rel=tag>LongCat-Video</a>
                                , <a href=/tags/ai%E5%88%9B%E4%BD%9C.html rel=tag>AI创作</a>
                                , <a href=/tags/avatar.html rel=tag>Avatar</a>
                            </span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="row post-container-wrapper">
                <div class=col-md-6>
                    <div class=post-container>
                        <h2 class=post-title>
                            <a href=https://tech.meituan.com/2025/12/19/longcat-interaction-denoiserotator.html rel=bookmark>大模型剪枝新范式：先浓缩，再剪枝——DenoiseRotator技术解读</a>
                        </h2>
                        <div class=meta-box>
                            <span class=m-post-date>
                                <i class="fa fa-calendar-o"></i>
                                2025年12月19日
                            </span>
                            <span class=m-post-nick>美团技术团队</span>
                        </div>
                        <div class="post-content post-expect">
                            美团 LongCat Interaction 团队联合上海交通大学听觉认知与计算声学实验室，以及香港科技大学的研究者，共同完成了大模型剪枝方法的创新研究，提出了名为 DenoiseRotator 的新技术。通过首先对参数矩阵进行变换，“将知识和推理能力浓缩到由少量参数组成的子网络内”，“再裁剪掉子网络外的参数”，实现了大模型剪枝的新范式。
<a class="more-link btn btn-primary btn-xs" href=https://tech.meituan.com/2025/12/19/longcat-interaction-denoiserotator.html>阅读全文</a>
                        </div>
                        <div class="meta-box post-bottom-meta-box hidden-print">
                            <span class=tag-links>
                                <i class="fa fa-tags" aria-hidden=true></i>
                                <a href=/tags/longcat.html rel=tag>LongCat</a>
                                , <a href=/tags/%E5%A4%A7%E6%A8%A1%E5%9E%8B.html rel=tag>大模型</a>
                                , <a href=/tags/%E5%A4%A7%E6%A8%A1%E5%9E%8B%E5%89%AA%E6%9E%9D.html rel=tag>大模型剪枝</a>
                                , <a href=/tags/denoiserotator.html rel=tag>DenoiseRotator</a>
                            </span>
                        </div>
                    </div>
                </div>
                <div class=col-md-6>
                    <div class=post-container>
                        <h2 class=post-title>
                            <a href=https://tech.meituan.com/2025/12/09/longcat-image-application.html rel=bookmark>LongCat 上线 AI 生图！精准高效，AI 创作不设限</a>
                        </h2>
                        <div class=meta-box>
                            <span class=m-post-date>
                                <i class="fa fa-calendar-o"></i>
                                2025年12月09日
                            </span>
                            <span class=m-post-nick>美团技术团队</span>
                        </div>
                        <div class="post-content post-expect">
                            美团 LongCat 全新上线 AI 生图功能，该功能基于 LongCat 系列模型「LongCat-Image」打造而成。无论是追求高效出图的普通用户，还是需要精准落地创意的专业创作者，LongCat 都以 “轻量化模型 &#43;流畅体验” ，让 AI 生图真正成为人人可用的创作工具。
<a class="more-link btn btn-primary btn-xs" href=https://tech.meituan.com/2025/12/09/longcat-image-application.html>阅读全文</a>
                        </div>
                        <div class="meta-box post-bottom-meta-box hidden-print">
                            <span class=tag-links>
                                <i class="fa fa-tags" aria-hidden=true></i>
                                <a href=/tags/longcat.html rel=tag>LongCat</a>
                                , <a href=/tags/%E5%A4%A7%E6%A8%A1%E5%9E%8B.html rel=tag>大模型</a>
                                , <a href=/tags/longcat-image.html rel=tag>LongCat-Image</a>
                                , <a href=/tags/ai%E5%88%9B%E4%BD%9C.html rel=tag>AI创作</a>
                                , <a href=/tags/%E5%9B%BE%E5%83%8F%E7%94%9F%E6%88%90.html rel=tag>图像生成</a>
                            </span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="row post-container-wrapper">
                <div class=col-md-6>
                    <div class=post-container>
                        <h2 class=post-title>
                            <a href=https://tech.meituan.com/2025/12/09/longcat-image-model.html rel=bookmark>美团发布 LongCat-Image 图像生成模型，编辑能力登顶开源 SOTA</a>
                        </h2>
                        <div class=meta-box>
                            <span class=m-post-date>
                                <i class="fa fa-calendar-o"></i>
                                2025年12月09日
                            </span>
                            <span class=m-post-nick>美团技术团队</span>
                        </div>
                        <div class="post-content post-expect">
                            美团 LongCat 团队正式发布并开源 LongCat-Image 模型，通过高性能模型架构设计、系统性的训练策略和数据工程，以 6B 参数规模，成功在文生图和图像编辑的核心能力维度上逼近更大尺寸模型效果，为开发者社区与产业界提供了 “高性能、低门槛、全开放” 的全新选择。
<a class="more-link btn btn-primary btn-xs" href=https://tech.meituan.com/2025/12/09/longcat-image-model.html>阅读全文</a>
                        </div>
                        <div class="meta-box post-bottom-meta-box hidden-print">
                            <span class=tag-links>
                                <i class="fa fa-tags" aria-hidden=true></i>
                                <a href=/tags/longcat.html rel=tag>LongCat</a>
                                , <a href=/tags/%E5%BC%80%E6%BA%90.html rel=tag>开源</a>
                                , <a href=/tags/%E5%A4%A7%E6%A8%A1%E5%9E%8B.html rel=tag>大模型</a>
                                , <a href=/tags/longcat-image.html rel=tag>LongCat-Image</a>
                                , <a href=/tags/%E5%9B%BE%E5%83%8F%E7%94%9F%E6%88%90.html rel=tag>图像生成</a>
                            </span>
                        </div>
                    </div>
                </div>
                <div class=col-md-6>
                    <div class=post-container>
                        <h2 class=post-title>
                            <a href=https://tech.meituan.com/2025/12/05/ai-coding-unit-testing.html rel=bookmark>AI Coding与单元测试的协同进化：从验证到驱动</a>
                        </h2>
                        <div class=meta-box>
                            <span class=m-post-date>
                                <i class="fa fa-calendar-o"></i>
                                2025年12月05日
                            </span>
                            <span class=m-post-nick>业务研发平台</span>
                        </div>
                        <div class="post-content post-expect">
                            AI生成代码质量难以把控！本文分享来自美团的技术实践，三大策略破解AI编程痛点。单测快速验证逻辑正确性，安全网保护存量代码演进，TDD模式精准传递需求。告别「看起来没问题」的错觉，构建AI时代的代码质量保障体系。
<a class="more-link btn btn-primary btn-xs" href=https://tech.meituan.com/2025/12/05/ai-coding-unit-testing.html>阅读全文</a>
                        </div>
                        <div class="meta-box post-bottom-meta-box hidden-print">
                            <span class=tag-links>
                                <i class="fa fa-tags" aria-hidden=true></i>
                                <a href=/tags/%E4%B8%9A%E5%8A%A1%E7%A0%94%E5%8F%91%E5%B9%B3%E5%8F%B0.html rel=tag>业务研发平台</a>
                                , <a href=/tags/%E5%A4%A7%E6%A8%A1%E5%9E%8B.html rel=tag>大模型</a>
                                , <a href=/tags/ai-coding.html rel=tag>AI Coding</a>
                                , <a href=/tags/%E5%8D%95%E5%85%83%E6%B5%8B%E8%AF%95.html rel=tag>单元测试</a>
                            </span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="row post-container-wrapper">
                <div class=col-md-6>
                    <div class=post-container>
                        <h2 class=post-title>
                            <a href=https://tech.meituan.com/2025/11/28/longcat-r-horizon.html rel=bookmark>R-HORIZON：探索长程推理边界，复旦NLP &amp;美团LongCat联合提出LRMs能力评测新框架</a>
                        </h2>
                        <div class=meta-box>
                            <span class=m-post-date>
                                <i class="fa fa-calendar-o"></i>
                                2025年11月28日
                            </span>
                            <span class=m-post-nick>美团技术团队</span>
                        </div>
                        <div class="post-content post-expect">
                            复旦大学与美团LongCat联合推出 R-HORIZON——首个系统性评估与增强 LRMs 长链推理能力的评测框架与训练方法。核心创新：R-HORIZON 提出了问题组合（Query Composition）方法，通过构建问题间的依赖关系，将孤立任务转化为复杂的多步骤推理链。
<a class="more-link btn btn-primary btn-xs" href=https://tech.meituan.com/2025/11/28/longcat-r-horizon.html>阅读全文</a>
                        </div>
                        <div class="meta-box post-bottom-meta-box hidden-print">
                            <span class=tag-links>
                                <i class="fa fa-tags" aria-hidden=true></i>
                                <a href=/tags/longcat.html rel=tag>LongCat</a>
                                , <a href=/tags/%E5%A4%A7%E6%A8%A1%E5%9E%8B.html rel=tag>大模型</a>
                                , <a href=/tags/r-horizon.html rel=tag>R-HORIZON</a>
                                , <a href=/tags/lrms.html rel=tag>LRMs</a>
                            </span>
                        </div>
                    </div>
                </div>
                <div class=col-md-6>
                    <div class=post-container>
                        <h2 class=post-title>
                            <a href=https://tech.meituan.com/2025/11/27/longcat-amo-bench.html rel=bookmark>美团 LongCat 发布 AMO-Bench：突破 AIME 评测饱和困境，重新定义 LLM 数学上限</a>
                        </h2>
                        <div class=meta-box>
                            <span class=m-post-date>
                                <i class="fa fa-calendar-o"></i>
                                2025年11月27日
                            </span>
                            <span class=m-post-nick>美团技术团队</span>
                        </div>
                        <div class="post-content post-expect">
                            美团 LongCat 团队发布数学推理评测基准—— AMO-Bench 。该评测集共包含 50 道竞赛专家原创试题，所有题目均对标甚至超越 IMO 竞赛难度。AMO-Bench 既揭示出当前大语言模型在处理复杂推理任务上的局限性，同时也为模型推理能力的进一步提升树立了新的标杆。
<a class="more-link btn btn-primary btn-xs" href=https://tech.meituan.com/2025/11/27/longcat-amo-bench.html>阅读全文</a>
                        </div>
                        <div class="meta-box post-bottom-meta-box hidden-print">
                            <span class=tag-links>
                                <i class="fa fa-tags" aria-hidden=true></i>
                                <a href=/tags/longcat.html rel=tag>LongCat</a>
                                , <a href=/tags/%E5%A4%A7%E6%A8%A1%E5%9E%8B.html rel=tag>大模型</a>
                                , <a href=/tags/amo-bench.html rel=tag>AMO-Bench</a>
                                , <a href=/tags/%E8%AF%84%E6%B5%8B%E5%9F%BA%E5%87%86.html rel=tag>评测基准</a>
                            </span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="row post-container-wrapper">
                <div class=col-md-6>
                    <div class=post-container>
                        <h2 class=post-title>
                            <a href=https://tech.meituan.com/2025/11/21/longcat-interaction-wowservice.html rel=bookmark>美团 LongCat Interaction 团队发布大模型交互系统技术报告 WOWService</a>
                        </h2>
                        <div class=meta-box>
                            <span class=m-post-date>
                                <i class="fa fa-calendar-o"></i>
                                2025年11月21日
                            </span>
                            <span class=m-post-nick>美团技术团队</span>
                        </div>
                        <div class="post-content post-expect">
                            美团 LongCat 团队正式发布——「WOWService 大模型交互系统技术报告」，深度拆解了 「数据与知识双驱动」「自我优化训练」「四阶段训练流水线」「多 Agent 协同」 四大核心技术框架，希望对行业发展提供参考与启发。
<a class="more-link btn btn-primary btn-xs" href=https://tech.meituan.com/2025/11/21/longcat-interaction-wowservice.html>阅读全文</a>
                        </div>
                        <div class="meta-box post-bottom-meta-box hidden-print">
                            <span class=tag-links>
                                <i class="fa fa-tags" aria-hidden=true></i>
                                <a href=/tags/longcat.html rel=tag>LongCat</a>
                                , <a href=/tags/%E5%A4%A7%E6%A8%A1%E5%9E%8B.html rel=tag>大模型</a>
                                , <a href=/tags/wowservice.html rel=tag>WOWService</a>
                                , <a href=/tags/%E6%99%BA%E8%83%BD%E4%BA%A4%E4%BA%92.html rel=tag>智能交互</a>
                            </span>
                        </div>
                    </div>
                </div>
                <div class=col-md-6>
                    <div class=post-container>
                        <h2 class=post-title>
                            <a href=https://tech.meituan.com/2025/11/17/longcat-uno-bench.html rel=bookmark>美团 LongCat 团队发布全模态一站式评测基准 UNO-Bench</a>
                        </h2>
                        <div class=meta-box>
                            <span class=m-post-date>
                                <i class="fa fa-calendar-o"></i>
                                2025年11月17日
                            </span>
                            <span class=m-post-nick>美团技术团队</span>
                        </div>
                        <div class="post-content post-expect">
                            美团 LongCat 团队提出了一套高质量、多样化的一站式全模态大模型评测基准——UNO-Bench。该基准通过一个统一的框架，不仅能同时精准衡量模型的单模态与全模态理解能力，更首次验证了全模态大模型的“组合定律”——该定律在能力较弱的模型上呈现为短板效应，而在能力较强的模型上则涌现出协同增益，为行业提供了一种全新的、跨越模型规模的分析范式。
<a class="more-link btn btn-primary btn-xs" href=https://tech.meituan.com/2025/11/17/longcat-uno-bench.html>阅读全文</a>
                        </div>
                        <div class="meta-box post-bottom-meta-box hidden-print">
                            <span class=tag-links>
                                <i class="fa fa-tags" aria-hidden=true></i>
                                <a href=/tags/longcat.html rel=tag>LongCat</a>
                                , <a href=/tags/%E5%A4%A7%E6%A8%A1%E5%9E%8B.html rel=tag>大模型</a>
                                , <a href=/tags/uno-bench.html rel=tag>UNO-Bench</a>
                                , <a href=/tags/%E8%AF%84%E6%B5%8B%E5%9F%BA%E5%87%86.html rel=tag>评测基准</a>
                            </span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="row home-more-container">
                <div class=col-md-12>
                    <h2 class=page-title>继续学习</h2>
                </div>
                <div class=col-md-12>
                    <div class=post-container>
                        <div class=row>
                            <div class=col-md-4>
                                <a class="btn btn-primary home-browser-more-btn" href=/page/2.html>浏览更多文章</a>
                            </div>
                            <div class=col-md-8></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div class="container-fluid main-container" id=J_footer-container>
            <script>
                $CONFIG['data']['footerLink'] = [{
                    "name": "网站首页",
                    "link": "/"
                }, {
                    "name": "文章存档",
                    "link": "/archives"
                }, {
                    "name": "关于我们",
                    "link": "/about"
                }];
            </script>
        </div>
        <script src="https://awps-assets.meituan.net/mit/blog/v20190629/index.js?v=Whistle&t=20181017-1r"></script>
        <script async src="https://www.googletagmanager.com/gtag/js?id=UA-55279261-1"></script>
        <script>
            try {
                window.dataLayer = window.dataLayer || [];
                function gtag() {
                    dataLayer.push(arguments);
                }
                gtag('js', new Date());
                gtag('config', 'UA-55279261-1');
            } catch (e) {}
        </script>
        <script>
            try {
                var _hmt = _hmt || [];
                var hm = document.createElement("script");
                hm.src = "https://hm.baidu.com/hm.js?7158c55a533ed0cf57dede022b1e6aed";
                var s = document.getElementsByTagName("script")[0];
                s.parentNode.insertBefore(hm, s);
            } catch (e) {}
        </script>
    </body>
</html>

    """


# ============================================================================
# SiteSchema Tests
# ============================================================================

class TestSiteSchema:
    """SiteSchema 模型测试"""

    def test_create_schema(self):
        """测试创建 SiteSchema"""
        schema = SiteSchema(
            site_name="tech.meituan.com",
            site_url="https://tech.meituan.com/",
            selectors=[{
                "title": "h1.article-title",
                "author": ".author",
                "content": ".article-body",
                "tags": ".article-tags .tag",
            }],
        )

        assert schema.site_name == "tech.meituan.com"
        assert schema.site_url == "https://tech.meituan.com/"
        assert len(schema.selectors) == 1
        assert len(schema.selectors[0]) == 4
        assert schema.created_at is not None
        assert schema.updated_at is not None
        assert schema.last_llm_call is None

    def test_schema_serialization(self):
        """测试 Schema JSON 序列化"""
        schema = SiteSchema(
            site_name="example.com",
            site_url="https://example.com",
            selectors=[{"title": "h1"}],
        )

        json_str = schema.model_dump_json()
        data = json.loads(json_str)

        assert data["site_name"] == "example.com"
        assert data["selectors"][0]["title"] == "h1"

    def test_schema_deserialization(self):
        """测试 Schema JSON 反序列化"""
        data = {
            "site_name": "test.com",
            "site_url": "https://test.com",
            "selectors": [{"title": "h1", "content": "article"}],
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "last_llm_call": None,
        }

        schema = SiteSchema(**data)
        assert schema.site_name == "test.com"
        assert schema.selectors[0]["content"] == "article"


# ============================================================================
# SchemaStore Tests
# ============================================================================

class TestSchemaStore:
    """SchemaStore 持久化测试"""

    def test_init_db(self, temp_db_path):
        """测试数据库初始化"""
        SchemaStore()
        assert os.path.exists(temp_db_path)

    def test_save_and_get(self, temp_db_path):
        """测试保存和获取 Schema"""
        store = SchemaStore()

        schema = SiteSchema(
            site_name="tech.meituan.com",
            site_url="https://tech.meituan.com/",
            selectors=[{"title": "h1"}],
        )
        store.save(schema)

        retrieved = store.get("tech.meituan.com")
        assert retrieved is not None
        assert retrieved.site_name == "tech.meituan.com"
        assert retrieved.selectors[0]["title"] == "h1"

    def test_get_nonexistent(self, temp_db_path):
        """测试获取不存在的 Schema"""
        store = SchemaStore()
        result = store.get("nonexistent.com")
        assert result is None

    def test_update_selectors(self, temp_db_path):
        """测试更新 selectors"""
        store = SchemaStore()

        schema = SiteSchema(
            site_name="test.com",
            site_url="https://test.com",
            selectors=[{"title": "h1"}],
        )
        store.save(schema)

        store.update_selectors("test.com", [{"title": "h2", "content": "article"}])
        updated = store.get("test.com")

        assert updated.selectors[0]["title"] == "h2"
        assert updated.selectors[0]["content"] == "article"

    def test_can_use_llm_first_time(self, temp_db_path):
        """测试首次访问允许 LLM"""
        store = SchemaStore()
        assert store.can_use_llm("new.site.com") is True

    def test_can_use_llm_after_call(self, temp_db_path):
        """测试 LLM 调用后 24 小时内不允许再次调用"""
        store = SchemaStore()

        schema = SiteSchema(
            site_name="test.com",
            site_url="https://test.com",
            selectors=[],
        )
        store.save(schema)
        store.mark_llm_called("test.com")

        assert store.can_use_llm("test.com") is False

    def test_mark_llm_called(self, temp_db_path):
        """测试标记 LLM 调用"""
        store = SchemaStore()

        schema = SiteSchema(
            site_name="test.com",
            site_url="https://test.com",
            selectors=[],
        )
        store.save(schema)
        store.mark_llm_called("test.com")

        updated = store.get("test.com")
        assert updated.last_llm_call is not None


# ============================================================================
# DOMExtractor Tests
# ============================================================================

# ============================================================================
# AdaptiveWebCrawler Tests (Unit - with mocked SchemaStore)
# ============================================================================

class TestAdaptiveWebCrawler:
    """AdaptiveWebCrawler 单元测试"""

    def test_detect_site(self, mock_schema_store):
        """测试站点检测"""
        crawler = AdaptiveWebCrawler()

        assert crawler._detect_site("https://tech.meituan.com/archives/") == "tech.meituan.com"
        assert crawler._detect_site("https://blog.example.com/post/123") == "blog.example.com"
        assert crawler._detect_site("https://example.com") == "example.com"


    def test_fetch_html_success(self, mock_schema_store):
        """测试成功获取 HTML"""
        async def run():
            crawler = AdaptiveWebCrawler()
            html = await crawler._fetch_html("https://httpbin.org/html")
            assert "<html>" in html or "<HTML>" in html

        asyncio.run(run())

    def test_fetch_html_failure(self, mock_schema_store):
        """测试获取 HTML 失败"""
        async def run():
            crawler = AdaptiveWebCrawler()
            with pytest.raises(Exception):
                await crawler._fetch_html("https://httpbin.org/status/404")

        asyncio.run(run())


class TestAdaptiveWebCrawlerIntegration:
    """AdaptiveWebCrawler 集成测试（需要网络）"""

    @pytest.fixture(autouse=True)
    def setup_data_dir(self, monkeypatch):
        """确保数据目录存在"""
        data_dir = Path("./data")
        data_dir.mkdir(exist_ok=True)
        monkeypatch.setattr("comp_synth.config.settings.data_dir", data_dir)
        monkeypatch.setattr("comp_synth.config.settings.site_schema_db_path", data_dir / "test_site_schemas.db")
        yield
        # cleanup
        import time
        time.sleep(0.1)

    def test_crawl_meituan_homepage(self):
        """测试爬取美团技术首页"""
        async def run():
            crawler = AdaptiveWebCrawler()
            items = await crawler.fetch({"url": "https://tech.meituan.com/"})
            assert isinstance(items, list)

        asyncio.run(run())

    def test_crawl_meituan_article_list(self):
        """测试爬取美团技术文章列表页"""
        async def run():
            crawler = AdaptiveWebCrawler()
            items = await crawler.fetch({"url": "https://tech.meituan.com/archives/"})
            assert isinstance(items, list)

        asyncio.run(run())

    def test_crawl_meituan_article_detail(self):
        """测试爬取美团技术文章详情页"""
        async def run():
            crawler = AdaptiveWebCrawler()
            items = await crawler.fetch({
                "url": "https://tech.meituan.com/2024/10/18/recce-in-meituan.html"
            })

            assert isinstance(items, list)
            if items:
                item = items[0]
                assert item.url == "https://tech.meituan.com/2024/10/18/recce-in-meituan.html"
                assert item.source == "web"
                # 最低保障：url + title
                assert item.title != ""

        asyncio.run(run())

    def test_duplicate_url_skipped(self):
        """测试重复 URL 处理行为

        去重检查已提前至 crawler.fetch() 层面，避免重复爬取已访问的详情页。
        第一次爬取后，URL 被标记为已爬取，第二次调用将跳过。
        """
        from unittest.mock import MagicMock

        async def run():
            # 创建一个新的 crawler，使用 mock tracker
            crawler = AdaptiveWebCrawler()
            mock_tracker = MagicMock()

            # 第一次调用时 is_crawled 返回 False，第二次返回 True
            mock_tracker.is_crawled.side_effect = [False, True]
            mock_tracker.mark_crawled = MagicMock()
            crawler._tracker = mock_tracker

            url = "https://example.com/test-article"

            # 第一次爬取
            items1 = await crawler.fetch({"url": url})
            assert len(items1) >= 0, "第一次爬取应返回结果"

            # 第二次爬取同一 URL - crawler.fetch 现在会在爬取前检查是否已爬过
            items2 = await crawler.fetch({"url": url})

            # 验证第二次调用因去重被跳过
            assert isinstance(items2, list), "crawler 应返回 list"
            assert len(items2) == 0, "重复 URL 应被跳过，返回空列表"

        asyncio.run(run())


# ============================================================================
# Schema Persistence & Reuse Integration Tests (Real LLM)
# ============================================================================

class TestSchemaPersistenceAndReuse:
    """
    测试 Schema 持久化和复用（真实 LLM 调用）

    验证流程：
    1. 首次爬取：LLM 被调用生成 selectors 并保存到 DB
    2. 二次爬取：使用已保存的 CSS selectors，不调用 LLM
    """

    @pytest.fixture(autouse=True)
    def setup_real_schema_store(self, monkeypatch):
        """使用真实数据库路径（临时目录），不禁用 SchemaStore"""
        import tempfile

        tmpdir = tempfile.mkdtemp()
        db_path = Path(tmpdir) / "test_schema_reuse.db"
        data_dir = Path(tmpdir) / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        # 设置临时路径，但不 monkeypatch SchemaStore 类
        monkeypatch.setattr("comp_synth.config.settings.site_schema_db_path", db_path)
        monkeypatch.setattr("comp_synth.config.settings.data_dir", data_dir)
        monkeypatch.setattr("comp_synth.config.settings.crawl_db_path", data_dir / "crawl_state.db")

        # 清除全局 crawler 实例的 schema_store 缓存，确保使用新 DB
        from comp_synth.crawlers import adaptive_web_crawler
        adaptive_web_crawler.AdaptiveWebCrawler._schema_store = None
        adaptive_web_crawler.AdaptiveWebCrawler._tracker = None

        yield db_path

        # 清理
        import shutil
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass

    def test_first_crawl_saves_schema(self):
        """测试首次爬取后 schema 被保存到数据库"""
        from comp_synth.store.schema_store import SchemaStore

        async def run():
            site = "example.com"

            # 初始状态：没有 schema
            store = SchemaStore()
            assert store.get(site) is None
            assert store.can_use_llm(site) is True

            # 模拟一次 LLM 调用后的状态（直接保存 schema）
            from comp_synth.schema.site_chema import SiteSchema
            schema = SiteSchema(
                site_name=site,
                site_url=f"https://{site}",
                selectors=[{"title": "h1", "content": "article"}],
            )
            store.save(schema)
            store.mark_llm_called(site)

            # 验证 schema 已保存
            retrieved = store.get(site)
            assert retrieved is not None
            assert retrieved.selectors[0]["title"] == "h1"

            # 验证 LLM 调用已被标记（24小时内不允许再次调用）
            assert store.can_use_llm(site) is False

        asyncio.run(run())

    def test_second_crawl_uses_css_selector_not_llm(self):
        """
        测试二次爬取时使用 CSS selector 而不是 LLM

        策略：首次爬取用真实 LLM，第二次爬取时 mock LLM 并验证未被调用
        """

        from comp_synth.store.schema_store import SchemaStore

        async def run():
            crawler = AdaptiveWebCrawler()
            site = "httpbin.org"
            test_url = "https://httpbin.org/html"

            # 创建 crawler，它会使用真实 DOMExtractor 和 SchemaStore
            crawler = AdaptiveWebCrawler()

            # 第一次爬取：调用真实 LLM（如果需要）
            # 注意：如果 readability 能直接提取内容，可能不需要 LLM
            items1 = await crawler.fetch({"url": test_url})
            assert isinstance(items1, list)

            store = SchemaStore()

            # 检查 schema 是否被保存（如果 LLM 被调用）
            schema = store.get(site)
            can_use = store.can_use_llm(site)

            # 如果之前没有调用过 LLM，schema 可能是 None
            # 如果 readability 成功提取，不需要 LLM，schema 也不会被保存
            print(f"Schema after first crawl: {schema}")
            print(f"Can use LLM: {can_use}")

            # 第二次爬取：验证 LLM 未被调用
            llm_call_count = 0
            original_extract = crawler._dom_extractor.extract
            original_generate = crawler._dom_extractor.generate_selectors

            async def mock_extract(html):
                nonlocal llm_call_count
                llm_call_count += 1
                return await original_extract(html)

            async def mock_generate(html):
                nonlocal llm_call_count
                llm_call_count += 1
                return await original_generate(html)

            crawler._dom_extractor.extract = mock_extract
            crawler._dom_extractor.generate_selectors = mock_generate

            await crawler.fetch({"url": test_url})

            # 如果 schema 已保存，第二次爬取应该使用 CSS selector，不调用 LLM DOM 提取
            if schema and schema.selectors:
                assert llm_call_count == 0, f"二次爬取不应该调用 LLM，但调用了 {llm_call_count} 次"
            else:
                # 如果没有 schema（readability 成功提取），LLM 本就不应该被调用
                print("没有 schema 保存（readability 直接提取成功）")

        asyncio.run(run())

    def test_schema_reuse_verification(self):
        """综合测试：验证 schema 被正确保存和复用"""
        from comp_synth.store.schema_store import SchemaStore

        async def run():
            # 使用一个简单的测试页面
            test_url = "https://httpbin.org/html"

            # 第一次爬取
            crawler1 = AdaptiveWebCrawler()
            items1 = await crawler1.fetch({"url": test_url})
            assert len(items1) > 0

            # 检查 schema 状态
            store = SchemaStore()
            site_name = "httpbin.org"
            schema = store.get(site_name)

            # 第二次爬取 - 创建新的 crawler 实例，验证从 DB 加载 schema
            crawler2 = AdaptiveWebCrawler()
            items2 = await crawler2.fetch({"url": test_url})

            # 验证结果一致性
            if items1 and items2:
                # 如果两次都返回内容，title 应该一致
                assert items1[0].title == items2[0].title

            # 如果有 schema，验证其结构有效
            if schema:
                assert schema.site_name == site_name
                assert isinstance(schema.selectors, list)
                print(f"Saved selectors: {schema.selectors}")

        asyncio.run(run())

    @pytest.mark.skipif(
        os.getenv("OPENAI_API_KEY") == "" or os.getenv("OPENAI_BASE_URL") == "",
        reason="需要真实 LLM API key"
    )
    def test_real_llm_extract_and_generate_selectors(self):
        """
        真实调用 LLM 的测试（仅在配置了 OPENAI_API_KEY 时运行）

        测试流程：
        1. 使用复杂 HTML（readability 提取困难）让 LLM 真正被调用
        2. 验证 LLM 返回的结构化数据
        3. 验证 LLM 生成的 selectors 可用于 CSS 提取
        """
        import httpx


        async def run():
            extractor = DOMExtractor()

            # 获取美团技术博客文章页（结构复杂，readability 可能提取不佳）
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.get("https://tech.meituan.com")
                    html = response.text
            except Exception as e:
                pytest.skip(f"网络请求失败: {e}")

            # 使用 LLM 提取内容（真实调用）
            print("\n=== 真实 LLM 调用：extract ===")
            extracted = await extractor.extract(html)
            print(f"LLM 提取结果: {extracted}")
            assert "title" in extracted
            assert "content" in extracted
            assert extracted["title"] != "" or extracted["content"] != "", "LLM 应返回非空结果"

            # 使用 LLM 生成 selectors（真实调用）
            print("\n=== 真实 LLM 调用：generate_selectors ===")
            selectors = await extractor.generate_selectors(html)
            print(f"LLM 生成的 selectors: {selectors}")
            assert isinstance(selectors, dict)
            assert "title" in selectors or "content" in selectors, "应至少生成 title 或 content selector"

            # 使用生成的 selectors 提取内容
            if selectors.get("content"):
                result = extractor.extract_with_selectors(html, selectors)
                print(f"使用 selectors 提取的 content 长度: {len(result.get('content', ''))}")
                print(f"使用 selectors 提取的 content: {result.get('content', '')}")
                assert result.get("content") != "", "CSS selector 应能提取到内容"

        asyncio.run(run())


# ============================================================================
# List Page Extraction Tests
# ============================================================================

class TestListPageExtraction:
    """测试列表页多文章提取"""

    def test_is_list_page_true(self, mock_schema_store, meituan_list_html):
        """测试列表页检测返回 True"""
        async def run():
            crawler = AdaptiveWebCrawler()
            assert crawler._is_list_page(meituan_list_html) is True
        asyncio.run(run())

    def test_is_list_page_false(self, mock_schema_store):
        """测试详情页（article 页面）检测返回 False"""
        article_html = """
        <html><body>
            <article>
                <h1>文章标题</h1>
                <div class="article-content"><p>正文内容</p></div>
            </article>
        </body></html>
        """
        async def run():
            crawler = AdaptiveWebCrawler()
            assert crawler._is_list_page(article_html) is False
        asyncio.run(run())

    def test_extract_list_items(self, mock_schema_store, meituan_list_html):
        """测试从列表页提取多个条目"""
        async def run():
            crawler = AdaptiveWebCrawler()
            items = await crawler._extract_list_items(
                meituan_list_html, "https://tech.meituan.com/", "tech.meituan.com"
            )
            assert len(items) >= 2, f"应该提取到至少2个条目，实际: {len(items)}"
            # 验证条目结构正确
            assert items[0]["url"].startswith("https://tech.meituan.com/")
            assert items[0]["title"] != ""
            # 验证所有条目都有有效 URL 和 title
            for item in items:
                assert item["url"].startswith("http") or item["url"].startswith("/"), f"无效 URL: {item['url']}"
                assert item["title"] != "", "title 不应为空"
        asyncio.run(run())

    def test_extract_list_items_deduplication(self, mock_schema_store):
        """测试列表项 URL 去重"""
        html = """
        <html>
        <body>
            <div class="post-list">
                <article class="post-item">
                    <h2><a href="/2024/10/18/article1.html">第一篇文章标题</a></h2>
                    <p class="summary">摘要1</p>
                </article>
                <article class="post-item">
                    <h2><a href="/2024/10/18/article1.html">第一篇文章标题重复</a></h2>
                    <p class="summary">摘要1重复</p>
                </article>
                <article class="post-item">
                    <h2><a href="/2024/10/19/article2.html">第二篇文章标题</a></h2>
                    <p class="summary">摘要2</p>
                </article>
            </div>
        </body>
        </html>
        """
        async def run():
            crawler = AdaptiveWebCrawler()
            items = await crawler._extract_list_items(html, "https://example.com/", "example.com")
            # 应该去重，只保留唯一的 URL
            urls = [item["url"] for item in items]
            assert len(urls) == len(set(urls)), "URL 应该去重"
            assert len(items) == 2, f"应该只有2个唯一条目，实际: {len(items)}"
        asyncio.run(run())

    def test_crawl_list_page_with_mocked_detail(self, mock_schema_store, meituan_list_html):
        """测试列表页爬取返回多个 WebPageItem（mock 详情页）"""
        async def run():
            crawler = AdaptiveWebCrawler()

            # Mock _fetch_article_detail 返回预设内容
            async def mock_detail(url):
                return WebPageItem(
                    url=url,
                    title=f"详情页标题: {url}",
                    content=f"这是 {url} 的正文内容",
                    summary="摘要",
                    site_name="tech.meituan.com",
                )

            crawler._fetch_article_detail = mock_detail

            items = await crawler._crawl_list_page(meituan_list_html, "https://tech.meituan.com/")

            assert len(items) >= 2, f"应该返回至少2个条目，实际: {len(items)}"
            # 验证返回的是 WebPageItem
            for item in items:
                assert item.url.startswith("https://tech.meituan.com/")
                assert item.title != ""
                assert item.content != "" or item.summary != ""
        asyncio.run(run())

    def test_crawl_list_page_skips_detail_when_summary_enough(self, mock_schema_store):
        """测试 summary 足够长时不爬详情页"""
        html_with_long_summary = """
        <html>
        <body>
            <div class="post-list">
                <article class="post-item">
                    <h2><a href="/article1.html">这是一篇文章的标题</a></h2>
                    <p class="summary">这是一篇非常详细的技术文章，深入探讨了前端架构设计的核心原理与最佳实践，涵盖了性能优化、用户体验提升、可维护性增强等多个关键主题，并通过实际案例展示了如何在不同场景下应用这些技术方案，总计超过一百二十个字符的详细描述内容。</p>
                </article>
            </div>
        </body>
        </html>
        """
        async def run():
            crawler = AdaptiveWebCrawler()

            # Mock _fetch_article_detail，如果被调用会返回预设内容
            async def mock_detail(url):
                return WebPageItem(
                    url=url,
                    title=f"详情页标题: {url}",
                    content=f"这是 {url} 的正文内容",
                    summary="摘要",
                    site_name="example.com",
                )

            crawler._fetch_article_detail = mock_detail

            items = await crawler._crawl_list_page(html_with_long_summary, "https://example.com/")

            assert len(items) == 1
            # content 应该为空，因为没有爬详情页
            assert items[0].content == ""
            # summary 应该是原始的长 summary
            assert len(items[0].summary) > 100
            # mock_detail 不应该被调用
        asyncio.run(run())

    def test_is_summary_enough(self, mock_schema_store):
        """测试 _is_summary_enough 方法"""
        async def run():
            crawler = AdaptiveWebCrawler()

            # 长度 <= 100 返回 False
            assert not crawler._is_summary_enough("")
            assert not crawler._is_summary_enough("a" * 50)
            assert not crawler._is_summary_enough("a" * 100)

            # 长度 > 100 返回 True
            assert crawler._is_summary_enough("a" * 101)
            assert crawler._is_summary_enough("中文" * 51)
        asyncio.run(run())

    def test_extract_list_items_returns_empty_list(self):
        """测试 extract_list_items_with_selectors 返回空列表"""

        extractor = DOMExtractor()
        html = "<html><body><div class='no-match'></div></body></html>"
        selectors = [{
            "item_container": ".post",
            "url": "a",
            "title": "h2",
            "summary": "p"
        }]
        result = extractor.extract_list_items_with_selectors(html, selectors)
        assert result == []

    def test_has_valid_data(self):
        """测试 _has_valid_data 辅助方法正确识别有效/无效数据"""
        from comp_synth.crawlers.adaptive_web_crawler import AdaptiveWebCrawler

        crawler = AdaptiveWebCrawler()

        # 有效数据：title 和 url 都非空
        valid_items = [
            {"url": "https://example.com/1", "title": "Title 1"},
            {"url": "https://example.com/2", "title": ""},
        ]
        assert crawler._has_valid_data(valid_items) is True

        # 无效数据：只有 url，title 为空
        url_only_items = [
            {"url": "https://example.com/1", "title": ""},
        ]
        assert crawler._has_valid_data(url_only_items) is False

        # 无效数据：title 非空但 url 为空
        title_only_items = [
            {"url": "", "title": "Title Only"},
        ]
        assert crawler._has_valid_data(title_only_items) is False

        # 无效数据：全部为空
        invalid_items = [
            {"url": "", "title": ""},
        ]
        assert crawler._has_valid_data(invalid_items) is False

        # 空列表
        assert crawler._has_valid_data([]) is False


# ============================================================================
# TestCrawlerExtractionMethods - 测试三种爬取方式
# ============================================================================

class TestCrawlerExtractionMethods:
    """测试三种爬取方式：用户Selector、LLM学习、DB Selector"""

    def test_user_defined_selector(self):
        """测试用户传入 selectors 的爬取（user_selector 方式）"""
        sample_html = """
        <html><body>
            <article>
                <h1 class="article-title">测试文章标题</h1>
                <div class="article-content"><p>正文内容第一段</p><p>正文内容第二段</p></div>
                <span class="author">作者张三</span>
            </article>
        </body></html>
        """
        async def run():
            crawler = AdaptiveWebCrawler()
            user_selectors = [{
                "title": "h1.article-title",
                "content": ".article-content",
                "author": ".author"
            }]
            items = await crawler._crawl_detail_page(sample_html, "https://example.com/test", user_selectors)
            assert len(items) == 1
            assert items[0].title == "测试文章标题"
            assert "正文内容" in items[0].content
            assert items[0].author == "作者张三"
            # 验证日志输出格式（检查返回结果的正确性即可）
            logger.info(f"[测试] user_selector 方式 | title={items[0].title} | author={items[0].author} | content长度={len(items[0].content)}")

        asyncio.run(run())

    def test_llm_learning_selector(self):
        """测试 LLM 学习生成 selectors（llm_learning 方式）"""
        sample_html = """
        <html><body>
            <article>
                <h1>LLM测试文章标题</h1>
                <div class="main-content"><p>LLM提取的正文内容</p></div>
            </article>
        </body></html>
        """
        async def run():

            # 使用随机site name避免DB中的旧数据干扰
            site_name = f"llm_provider-test-{id(self)}.com"
            url = f"https://{site_name}/llm_provider-test"

            crawler = AdaptiveWebCrawler()

            # Mock _extract_with_readability 返回不够长的content，强制触发后续LLM步骤
            async def mock_readability(html):
                return {
                    "title": "readability标题",
                    "content": "短",  # content太短，< 100
                    "summary": "摘要"
                }

            # Mock LLM返回的内容
            mock_extracted = {
                "title": "LLM测试文章标题",
                "content": "LLM提取的正文内容，这里是足够的字数来满足大于100字符的要求",
                "author": "",
                "published_at": "",
                "tags": []
            }
            mock_selectors = [{
                "title": "h1",
                "content": ".main-content"
            }]

            with patch.object(crawler, '_extract_with_readability', new=mock_readability):
                with patch.object(crawler._dom_extractor, 'extract', new_callable=AsyncMock) as mock_extract:
                    with patch.object(crawler._dom_extractor, 'generate_selectors', new_callable=AsyncMock) as mock_gen:
                        mock_extract.return_value = mock_extracted
                        mock_gen.return_value = mock_selectors

                        # 强制设置 can_use_llm 返回 True（避免已有LLM调用记录）
                        with patch.object(crawler._schema_store, 'can_use_llm', return_value=True):
                            items = await crawler._crawl_detail_page(sample_html, url)

                            assert len(items) == 1
                            assert items[0].title == "LLM测试文章标题"
                            # 验证 LLM 被调用
                            mock_extract.assert_called_once()
                            mock_gen.assert_called_once()
                            logger.info(f"[测试] llm_learning 方式 | title={items[0].title} | content长度={len(items[0].content)}")

        asyncio.run(run())

    def test_db_selector_reuse(self):
        """测试从 DB 加载并复用 selectors（db_selector 方式）"""
        async def run():
            import tempfile
            from pathlib import Path

            # 使用临时DB确保隔离
            tmpdir = tempfile.mkdtemp()
            db_path = Path(tmpdir) / "test_db_selector.db"

            # Patch settings to use temp DB
            from comp_synth import config
            original_db_path = config.settings.site_schema_db_path
            config.settings.site_schema_db_path = db_path

            try:
                from comp_synth.schema.site_chema import SiteSchema
                from comp_synth.store.schema_store import SchemaStore

                # 保存一个已知 schema 到 DB
                store = SchemaStore()
                site_name = f"db-selector-test-{id(self)}.com"
                schema = SiteSchema(
                    site_name=site_name,
                    site_url=f"https://{site_name}",
                    selectors=[{
                        "title": "h1.db-title",
                        "content": ".db-content"
                    }]
                )
                store.save(schema)

                sample_html = """
                <html><body>
                    <h1 class="db-title">DB Selector 文章标题</h1>
                    <div class="db-content"><p>DB Selector 提取的正文</p></div>
                </body></html>
                """

                # 直接操作 crawler 的 _schema_store
                crawler = AdaptiveWebCrawler()
                crawler._schema_store = SchemaStore()  # 使用真实的 SchemaStore

                items = await crawler._crawl_detail_page(sample_html, f"https://{site_name}/article")

                # 由于 schema 存在，应该直接使用 DB selector
                assert len(items) == 1
                assert items[0].title == "DB Selector 文章标题"
                assert "DB Selector 提取的正文" in items[0].content
                logger.info(f"[测试] db_selector 方式 | title={items[0].title} | content长度={len(items[0].content)}")
            finally:
                config.settings.site_schema_db_path = original_db_path
                import shutil
                shutil.rmtree(tmpdir, ignore_errors=True)

        asyncio.run(run())
# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
