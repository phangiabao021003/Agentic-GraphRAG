import requests
from bs4 import BeautifulSoup

# Đường link URL bạn muốn lấy văn bản
url = "https://www.bhf.org.uk/informationsupport/heart-matters-magazine/nutrition/ask-the-expert/macronutrients"  # Thay bằng URL của bạn

# Gửi yêu cầu GET tới URL
response = requests.get(url)

# Kiểm tra xem yêu cầu có thành công hay không
if response.status_code == 200:
    # Phân tích nội dung HTML của trang
    soup = BeautifulSoup(response.content, "html.parser")
    
    # Lấy toàn bộ văn bản từ thẻ <body>
    text = soup.get_text(separator="", strip=True)
    
    # In ra văn bản
    print(text)
else:
    print(f"Failed to retrieve the page. Status code: {response.status_code}")
