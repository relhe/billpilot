# Billpilot Application

This project is a **Full Stack Payment Management Application** that allows users to manage a list of payments via user interface with CRUD functionality, evidence file uploads, and more. It includes both a **backend** (FastAPI) and a **frontend** (Angular 18+).

---

## Features

### Backend

- **CRUD Operations**:
  - Create, read, update, and delete payments.
- **File Uploads**:
  - Upload evidence files (PDF, PNG, JPG) when marking payments as completed.
  - Download uploaded evidence files.
- **Data Normalization**:
  - Normalize payment data from a CSV file and store it in MongoDB.
- **Dynamic Status Updates**:
  - Automatically update payment statuses (e.g., `due_now`, `overdue`) based on due dates.
- **Server-side Pagination and Filtering**:
  - Fetch paginated and filtered payment data with search capabilities.
- **Total Due Calculation**:
  - Dynamically calculate `total_due` using discount and tax percentages.

### Frontend (Angular 15+)

- **Payment Management UI**:
  - Search payments with filters.
  - View detailed payment information.
  - Create, update, and delete payments.
  - Upload and download evidence files.
- **Dynamic Status Management**:
  - Prevent setting a status to `completed` without an evidence file.
- **Address and Currency Auto-complete**:
  - Use APIs to auto-complete and validate fields.
- **Responsive Design**:
  - User-friendly and responsive for various devices.

---

## Installation

### Prerequisites

- Python 3.10+
- Angular 19
- MongoDB

### Backend Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/relhe/billpilot.git
   cd billpilot/back-end
   ```
2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # For Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the FastAPI server:
   ```bash
   uvicorn main:app --reload
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd ../front-end
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the Angular development server:
   ```bash
   ng serve
   ```

---

## Usage

### Backend Endpoints

- **GET /payment**: Fetch paginated and filtered payment data.
- **POST /payment**: Create a new payment.
- **PUT /payment/{payment_id}**: Update payment details.
- **DELETE /payment/{payment_id}**: Delete a payment by ID.
- **POST /**: Upload evidence files for a payment.

### Frontend Features

- Search, view, add, edit, and delete payments.
- Upload/download evidence files.
- Dynamic pagination and filtering.

---

## Project Structure

```
/billpilot
│
├── backend
│   ├── main.py
│   ├── models.py
│   ├── database.py
│   ├── requirements.txt
│
├── frontend
│   ├── src
│   ├── angular.json
│   ├── package.json
│   ├── tsconfig.json
│
└── README.md
```

## License

This project is licensed under the MIT License.

---

## Contact

For questions or suggestions, please reach out to:

- Email: renellherisson@gmail.com
