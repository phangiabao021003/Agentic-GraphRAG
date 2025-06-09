from qdrant_client import QdrantClient

def get_unique_doc_ids(client:QdrantClient,collection_name: str, limit: int = 100):
    all_doc_ids = set()  # Sử dụng set để loại bỏ doc_id trùng lặp
    scroll_offset = None  # Biến để lưu trữ vị trí scroll

    while True:
        # Lấy dữ liệu từ Qdrant
        response = client.scroll(
            collection_name=collection_name,
            scroll_filter=None,  # Không sử dụng filter
            limit=limit,  # Số lượng điểm lấy mỗi lần
            offset=scroll_offset,  # Vị trí bắt đầu scroll
            with_payload=True,  # Bao gồm payload để lấy doc_id
            with_vectors=False  # Không lấy vectors
        )
        
        # Duyệt qua các điểm (points) trả về
        points = response[0]
        if not points:
            break  # Nếu không còn dữ liệu thì thoát vòng lặp

        # Lấy doc_id từ metadata trong payload
        for point in points:
            metadata = point.payload.get("metadata", {})  # Lấy metadata từ payload
            doc_id = metadata.get("doc_id")  # Lấy doc_id từ metadata
            if doc_id:
                all_doc_ids.add(doc_id)  # Thêm doc_id vào set (để tránh trùng lặp)

        # Lấy scroll_offset để tiếp tục phân trang
        scroll_offset = response[1]
        if scroll_offset is None:
            break  # Nếu không còn dữ liệu thì thoát

    return sorted(all_doc_ids)

# Lấy các doc_id duy nhất từ collection
vectordb =  QdrantClient(host="localhost", port=6333)
doc_ids = get_unique_doc_ids(vectordb,"human-nutrition-text.pdf",100)
print(doc_ids)


