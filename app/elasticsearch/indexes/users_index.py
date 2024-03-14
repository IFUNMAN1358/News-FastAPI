users_index = {
        "settings": {
            "analysis": {
              "analyzer": {
                "custom_analyzer": {
                  "type": "custom",
                  "tokenizer": "standard",
                  "filter": ["lowercase", "edge_ngram_filter"]
                }
              },
              "filter": {
                "edge_ngram_filter": {
                  "type": "edge_ngram",
                  "min_gram": 2,
                  "max_gram": 10
                }
              }
            }
          },
        "mappings": {
            "properties": {
                "username": {
                    "type": "text",
                    "analyzer": "custom_analyzer",
                    "fields": {
                        "keyword": {
                            "type": "keyword"
                        }
                    }
                }
            }
        }
}
