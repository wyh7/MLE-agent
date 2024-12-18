import uuid
import os.path
from datetime import datetime
from typing import List, Dict, Optional

import lancedb
from lancedb.embeddings import get_registry

import chromadb
from chromadb.utils import embedding_functions

from mle.utils import get_config

chromadb.logger.setLevel(chromadb.logging.ERROR)


class ChromaDBMemory:

    def __init__(
            self,
            project_path: str,
            embedding_model: str = "text-embedding-ada-002"
    ):
        """
        Memory: memory and external knowledge management.
        Args:
            project_path: the path to store the data.
            embedding_model: the embedding model to use, default will use the embedding model from ChromaDB,
             if the OpenAI has been set in the configuration, it will use the OpenAI embedding model
             "text-embedding-ada-002".
        """
        self.db_name = '.mle'
        self.collection_name = 'memory'
        self.client = chromadb.PersistentClient(path=os.path.join(project_path, self.db_name))

        config = get_config(project_path)
        # use the OpenAI embedding function if the openai section is set in the configuration.
        if config['platform'] == 'OpenAI':
            self.client.get_or_create_collection(
                self.collection_name,
                embedding_function=embedding_functions.OpenAIEmbeddingFunction(
                    model_name=embedding_model,
                    api_key=config['api_key']
                )
            )
        else:
            self.client.get_or_create_collection(self.collection_name)

    def add_query(
            self,
            queries: List[Dict[str, str]],
            collection: str = None,
            idx: List[str] = None
    ):
        """
        add_query: add the queries to the memery.
        Args:
            queries: the queries to add to the memery. Should be in the format of
                {
                    "query": "the query",
                    "response": "the response"
                }
            collection: the name of the collection to add the queries.
            idx: the ids of the queries, should be in the same length as the queries.
            If not provided, the ids will be generated by UUID.

        Return: A list of generated IDs.
        """
        if idx:
            ids = idx
        else:
            ids = [str(uuid.uuid4()) for _ in range(len(queries))]

        if not collection:
            collection = self.collection_name

        query_list = [query['query'] for query in queries]
        added_time = datetime.now().isoformat()
        resp_list = [{'response': query['response'], 'created_at': added_time} for query in queries]
        # insert the record into the database
        self.client.get_or_create_collection(collection).add(
            documents=query_list,
            metadatas=resp_list,
            ids=ids
        )

        return ids

    def query(self, query_texts: List[str], collection: str = None, n_results: int = 5):
        """
        query: query the memery.
        Args:
            query_texts: the query texts to search in the memery.
            collection: the name of the collection to search.
            n_results: the number of results to return.

        Returns: the top k results.
        """
        if not collection:
            collection = self.collection_name
        return self.client.get_or_create_collection(collection).query(query_texts=query_texts, n_results=n_results)

    def peek(self, collection: str = None, n_results: int = 20):
        """
        peek: peek the memery.
        Args:
            collection: the name of the collection to peek.
            n_results: the number of results to return.

        Returns: the top k results.
        """
        if not collection:
            collection = self.collection_name
        return self.client.get_or_create_collection(collection).peek(limit=n_results)

    def get(self, collection: str = None, record_id: str = None):
        """
        get: get the record by the id.
        Args:
            record_id: the id of the record.
            collection: the name of the collection to get the record.

        Returns: the record.
        """
        if not collection:
            collection = self.collection_name
        collection = self.client.get_collection(collection)
        if not record_id:
            return collection.get()

        return collection.get(record_id)

    def delete(self, collection_name=None):
        """
        delete: delete the memery collections.
        Args:
            collection_name: the name of the collection to delete.
        """
        if not collection_name:
            collection_name = self.collection_name
        return self.client.delete_collection(name=collection_name)

    def count(self, collection_name=None):
        """
        count: count the number of records in the memery.
        Args:
            collection_name: the name of the collection to count.
        """
        if not collection_name:
            collection_name = self.collection_name
        return self.client.get_collection(name=collection_name).count()

    def reset(self):
        """
        reset: reset the memory.
        Notice: You may need to set the environment variable `ALLOW_RESET` to `TRUE` to enable this function.
        """
        self.client.reset()


class LanceDBMemory:

    def __init__(
        self,
        project_path: str,
    ):
        """
        Memory: A base class for memory and external knowledge management.
        Args:
            project_path: the path to store the data.
        """
        self.db_name = '.mle'
        self.table_name = 'memory'
        self.client = lancedb.connect(uri=self.db_name)

        config = get_config(project_path)
        if config["platform"] == "OpenAI":
            self.text_embedding = get_registry().get("openai").create(api_key=config["api_key"])
        else:
            raise NotImplementedError

    def add(
        self,
        texts: List[str],
        metadata: Optional[List[Dict]] = None,
        table_name: Optional[str] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Adds a list of text items to the specified memory table in the database.

        Args:
            texts (List[str]): A list of text strings to be added.
            metadata (Optional[List[Dict]]): A list of metadata to be added.
            table_name (Optional[str]): The name of the table to add data to. Defaults to self.table_name.
            ids (Optional[List[str]]): A list of unique IDs for the text items.
                If not provided, random UUIDs are generated.

        Returns:
            List[str]: A list of IDs associated with the added text items.
        """
        if isinstance(texts, str):
            texts = (texts, )

        if metadata is None:
            metadata = [None, ] * len(texts)
        elif isinstance(metadata, dict):
            metadata = (metadata, )
        else:
            assert len(texts) == len(metadata)

        embeds = self.text_embedding.compute_source_embeddings(texts)

        table_name = table_name or self.table_name
        ids = ids or [str(uuid.uuid4()) for _ in range(len(texts))]

        data = [
            {
                "vector": embed,
                "text": text,
                "id": idx,
                "metadata": meta,
            } for idx, text, embed, meta in zip(ids, texts, embeds, metadata)
        ]

        if table_name not in self.client.table_names():
            self.client.create_table(table_name, data=data)
        else:
            self.client.open_table(table_name).add(data=data)

        return ids

    def query(self, query_texts: List[str], table_name: Optional[str] = None, n_results: int = 5) -> List[List[dict]]:
        """
        Queries the specified memory table for similar text embeddings.

        Args:
            query_texts (List[str]): A list of query text strings.
            table_name (Optional[str]): The name of the table to query. Defaults to self.table_name.
            n_results (int): The maximum number of results to retrieve per query. Default is 5.

        Returns:
            List[List[dict]]: A list of results for each query text, each result being a dictionary with
            keys such as "vector", "text", and "id".
        """
        table_name = table_name or self.table_name
        table = self.client.open_table(table_name)
        query_embeds = self.text_embedding.compute_source_embeddings(query_texts)

        results = [table.search(query).limit(n_results).to_list() for query in query_embeds]
        return results

    def delete(self, record_id: str, table_name: Optional[str] = None) -> bool:
        """
        Deletes a record from the specified memory table.

        Args:
            record_id (str): The ID of the record to delete.
            table_name (Optional[str]): The name of the table to delete the record from. Defaults to self.table_name.

        Returns:
            bool: True if the deletion was successful, False otherwise.
        """
        table_name = table_name or self.table_name
        table = self.client.open_table(table_name)
        return table.delete(f"id = '{record_id}'")

    def drop(self, table_name: Optional[str] = None) -> bool:
        """
        Drops (deletes) the specified memory table.

        Args:
            table_name (Optional[str]): The name of the table to delete. Defaults to self.table_name.

        Returns:
            bool: True if the table was successfully dropped, False otherwise.
        """
        table_name = table_name or self.table_name
        return self.client.drop_table(table_name)

    def count(self, table_name: Optional[str] = None) -> int:
        """
        Counts the number of records in the specified memory table.

        Args:
            table_name (Optional[str]): The name of the table to count records in. Defaults to self.table_name.

        Returns:
            int: The number of records in the table.
        """
        table_name = table_name or self.table_name
        table = self.client.open_table(table_name)
        return table.count_rows()

    def reset(self) -> None:
        """
        Resets the memory by dropping the default memory table.
        """
        self.drop()
