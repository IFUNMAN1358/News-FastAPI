from elasticsearch import AsyncElasticsearch
from app.config import Config

elastic = AsyncElasticsearch(
    hosts=Config.elasticsearch_url
)
