"""Canonical skills, maintenance categories, and explicit spelling aliases.

Insertion order is the extraction order. Keep the original Data/AI order stable
and append new concepts. Categories never imply skills or job roles. Canonical
names are automatically aliases, so only additional spellings are listed here.
"""

SKILL_DEFINITIONS = {
    "Python": ("language", ("파이썬",)),
    "SQL": ("query_language", ("쿼리",)),
    "R": ("language", ()),
    "Java": ("language", ("자바",)),
    "Pandas": ("data_analysis", ()),
    "NumPy": ("data_analysis", ()),
    "Statistics": ("analytics", ("통계", "통계학", "통계분석")),
    "A/B Test": ("analytics", ("ab test", "a-b test", "ab테스트", "a/b테스트")),
    "Excel": ("analytics_bi", ("엑셀",)),
    "Tableau": ("analytics_bi", ("태블로",)),
    "Power BI": ("analytics_bi", ("powerbi",)),
    "Looker": ("analytics_bi", ()),
    "Plotly": ("data_visualization", ()),
    "Spark": ("data_engineering", ("스파크",)),
    "Airflow": ("data_engineering", ()),
    "Kafka": ("messaging_streaming", ("카프카",)),
    "Docker": ("containers", ("도커",)),
    "Kubernetes": ("containers", ("k8s", "쿠버네티스")),
    "AWS": ("cloud", ("amazon web services",)),
    "GCP": ("cloud", ("google cloud", "google cloud platform")),
    "Azure": ("cloud", ("microsoft azure",)),
    "MySQL": ("database", ()),
    "PostgreSQL": ("database", ("postgres",)),
    "MongoDB": ("database", ("mongo db",)),
    "Machine Learning": ("ai_ml", ("머신러닝", "머신 러닝", "ml")),
    "Deep Learning": ("ai_ml", ("딥러닝", "딥 러닝")),
    "NLP": ("ai_ml", ("자연어", "자연어처리", "자연어 처리", "natural language processing")),
    "PyTorch": ("ai_ml", ("파이토치",)),
    "TensorFlow": ("ai_ml", ("텐서플로", "텐서플로우")),
    "Recommender System": ("ai_ml", ("추천시스템", "추천 시스템")),
    "GA4": ("analytics", ("google analytics 4",)),
    "Kotlin": ("language", ("코틀린",)),
    "JavaScript": ("language", ("자바스크립트",)),
    "TypeScript": ("language", ("타입스크립트",)),
    "Spring": ("backend_framework", ("스프링",)),
    "Spring Boot": ("backend_framework", ("springboot", "spring-boot", "스프링부트", "스프링 부트")),
    "Spring MVC": ("backend_framework", ("springmvc", "스프링 mvc")),
    "Spring Security": ("backend_framework", ("springsecurity", "스프링 시큐리티", "스프링시큐리티")),
    "JPA": ("persistence", ("java persistence api", "jakarta persistence api")),
    "Hibernate": ("persistence", ("하이버네이트",)),
    "QueryDSL": ("persistence", ("query dsl", "쿼리dsl")),
    "Gradle": ("build_tool", ("그래들",)),
    "Maven": ("build_tool", ("메이븐",)),
    "MariaDB": ("database", ("maria db",)),
    "Oracle": ("database", ("oracle database", "오라클")),
    "Redis": ("cache", ("레디스",)),
    "Elasticsearch": ("search", ("elastic search", "엘라스틱서치")),
    "RabbitMQ": ("messaging_streaming", ("rabbit mq", "래빗엠큐")),
    "Linux": ("operating_system", ("리눅스",)),
    "REST API": ("api_web", ("restapi", "restful api")),
    "GraphQL": ("api_web", ("graph ql",)),
    "JWT": ("api_security", ("json web token",)),
    "OAuth": ("api_security", ("oauth2", "oauth 2", "oauth 2.0", "oauth2.0")),
    "Git": ("version_control", ("깃",)),
    "GitHub Actions": ("ci_cd", ("githubactions", "github-actions", "깃허브 액션", "깃허브액션")),
    "Jenkins": ("ci_cd", ("젠킨스",)),
    "CI/CD": ("ci_cd", ("ci / cd", "ci-cd", "cicd")),
    "JUnit": ("testing", ("junit5", "junit 5", "junit4", "junit 4")),
    "Mockito": ("testing", ()),
}

SKILL_ALIASES = {
    canonical: (canonical, *aliases)
    for canonical, (_, aliases) in SKILL_DEFINITIONS.items()
}
