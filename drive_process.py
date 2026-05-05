import os
import io
from dotenv import load_dotenv

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/drive"]

INPUT_FOLDER_ID = os.getenv("DRIVE_INPUT_FOLDER_ID")
OUTPUT_FOLDER_ID = os.getenv("DRIVE_OUTPUT_FOLDER_ID")
PROCESSED_FILE = "processed_ids.txt"


def load_processed_ids():
    if not os.path.exists(PROCESSED_FILE):
        return set()

    with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())


def get_drive_service():
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json",
            SCOPES
        )
        creds = flow.run_local_server(port=0)

        with open("token.json", "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


def list_images_in_input_folder(service):
    query = (
        f"'{INPUT_FOLDER_ID}' in parents "
        "and trashed = false "
        "and mimeType contains 'image/'"
    )

    results = service.files().list(
        q=query,
        fields="files(id, name, mimeType)",
        pageSize=50
    ).execute()

    return results.get("files", [])


def main():
    print("Drive確認開始")
    print("INPUT_FOLDER_ID:", INPUT_FOLDER_ID)
    print("OUTPUT_FOLDER_ID:", OUTPUT_FOLDER_ID)

    processed_ids = load_processed_ids()
    print("処理済みID数:", len(processed_ids))

    service = get_drive_service()
    files = list_images_in_input_folder(service)

    print("取得ファイル数:", len(files))

    if not files:
        print("このフォルダ直下に画像が見つかりません")
        return

    print("取得した画像一覧:")

    for file in files:
        status = "処理済み" if file["id"] in processed_ids else "未処理"
        print(f"- {file['name']} / {file['mimeType']} / {status}")


if __name__ == "__main__":
    main()