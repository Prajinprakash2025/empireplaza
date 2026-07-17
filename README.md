# Empire Plaza - Food Delivery Backend API

Empire Plaza is a multi-module food delivery web application built using **Python Django** and **Django REST Framework (DRF)**. It features role-based access control for four distinct modules: Admins, Users (Customers), Employees (Kitchen Staff), and Delivery Boys.

The application uses **JWT (JSON Web Tokens)** for secure, stateless authentication and supports **Phone & OTP-based login**. It is fully containerized using **Docker** and configured for easy deployment on a VPS (Virtual Private Server).

---

## Tech Stack
* **Framework:** Django & Django REST Framework (DRF)
* **Authentication:** JWT (SimpleJWT) with Phone + OTP verification
* **Database:** SQLite (Local Development) / PostgreSQL (Production)
* **Containerization:** Docker & Docker Compose
* **API Architecture:** RESTful API

---

## Features & Modules

### 1. Authentication
* Passwordless Phone Number + OTP registration and login.
* Token refresh mechanism to keep users logged in seamlessly.
* Expiry protection for OTP codes (expires in 5 minutes).

### 2. User Module (Food Ordering)
* Browse categories and food menus.
* Place orders and track live order status.
* View order history.

### 3. Admin Module
* Manage categories and food items (CRUD).
* Track all active and completed orders.
* Assign delivery boys to orders.

### 4. Employee Module (Kitchen Dashboard)
* View incoming orders that need preparation.
* Change order status (e.g., to "Preparing", "Ready for Pickup").

### 5. Delivery Boy Module
* Browse orders ready for delivery.
* Accept deliveries (updates status to "Out for Delivery").
* Mark orders as "Delivered" upon completion.

---

## Local Development Setup

### Option 1: Running with Docker (Recommended)
Make sure you have [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.

1. **Clone the repository:**
   ```bash
   git clone <your-repository-url>
   cd empaire_plaza/backend