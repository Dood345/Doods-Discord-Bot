# **Deploying Your Discord Bot to Google Cloud**

This guide provides two methods for deploying this bot to Google Cloud for free, 24/7 hosting.

*   **Method 1: Google Cloud Run (Recommended)**: A modern, low-maintenance approach that runs your bot in a managed container. Best for most users.
*   **Method 2: Google Compute Engine (Alternative)**: A traditional virtual machine (VM) that gives you full control over the operating system.

## **Prerequisites**

Before you begin, you will need:

1.  A **Google Cloud Account** with billing enabled. You won't be charged if you stay within the "Always Free" tier limits.
2.  The **gcloud command-line tool** installed and configured on your local machine.
3.  **Git** installed on your local machine.
4.  **Docker Desktop** installed and running on your local machine (for the Cloud Run method).

## **Method 1: Google Cloud Run (Recommended)**

This method packages your bot into a container and runs it on a managed, serverless platform.

### **Step 1: Prepare Your Code for Containerization**

Cloud Run requires your application to be containerized and to respond to a basic health check.

**1. Create a Dockerfile**

In the root directory of your project, create a file named `Dockerfile` (no extension) with the following content:

```dockerfile
# Use an official lightweight Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Command to run your bot when the container starts
CMD ["python", "main.py"]
```

**2. Add a Health Check Server**

Cloud Run needs to know your application has started successfully. We'll add a lightweight Flask web server that runs in the background.

*   **Update requirements.txt:** Add `Flask` to your requirements file.
    ```text
    # ... your other dependencies ...
    Flask==3.0.0
    ```

*   **Update discord_bot/main.py:** Add the following code to your main bot script.
    ```python
    # ADD THESE IMPORTS AT THE TOP OF YOUR FILE
    import os
    from flask import Flask
    from threading import Thread

    # ... your existing bot code ...

    # ADD THIS 'keep_alive' CODE BLOCK *BEFORE* YOUR bot.run() LINE
    app = Flask('')

    @app.route('/')
    def home():
        return "Bot is alive!"

    def run_server():
      # Cloud Run provides the PORT environment variable
      port = int(os.environ.get("PORT", 8080))
      app.run(host='0.0.0.0', port=port)

    def keep_alive():
        t = Thread(target=run_server)
        t.start()

    # MODIFY YOUR FINAL LINES TO LOOK LIKE THIS
    if __name__ == "__main__":
        keep_alive() # Starts the web server

        # Your original bot startup logic
        token = os.getenv('DISCORD_TOKEN')
        bot = YourBotClass() # Replace with your bot's class
        bot.run(token)
    ```

### **Step 2: Build and Push the Container Image**

Next, we build the container and store it in Google's Artifact Registry.

1.  **Enable the Artifact Registry API:**
    ```bash
    gcloud services enable artifactregistry.googleapis.com
    ```

2.  **Create a Docker Repository:**
    ```bash
    gcloud artifacts repositories create <your-repo-name> --repository-format=docker --location=us-central1 --description="Docker repository for Discord bots"
    ```
    *(Replace `your-repo-name` with a name like `discord-bots`)*

3.  **Build the Local Image:** Build the image with a simple, memorable name.
    ```bash
    docker build -t <image-name> .
    ```

4.  **Tag the Image for Artifact Registry:** Apply the full "address" tag to the image you just built. Replace `your-gcp-project-id` and `your-repo-name`.
    ```bash
    docker tag doods-discord-bot us-central1-docker.pkg.dev/<your-gcp-project-id>/<your-repo-name>/<image-name>
    ```

5.  **Push the Tagged Image:**
    ```bash
    docker push us-central1-docker.pkg.dev/<your-gcp-project-id>/<your-repo-name>/<image-name>
    ```

### **Step 3: Deploy to Cloud Run**

Run this single command to deploy your bot. Replace the placeholders with your actual values (Project ID, Repo Name, and your new secure tokens).

```bash
gcloud run deploy doods-discord-bot \
  --image=us-central1-docker.pkg.dev/<your-gcp-project-id>/<your-repo-name>/<image-name> \
  --set-env-vars="DISCORD_TOKEN=YOUR_DISCORD_TOKEN,GEMINI_API_KEY=YOUR_GEMINI_KEY" \
  --min-instances=1 \
  --no-cpu-throttling \
  --no-allow-unauthenticated \
  --region=us-central1
```

**Flag Explanation:**

*   `--min-instances=1` & `--no-cpu-throttling`: These flags work together to keep your bot's container running 24/7, which is essential for a Discord bot.
*   `--no-allow-unauthenticated`: Secures your service since it doesn't need to be accessed publicly over the web.

### **Step 4: Check Logs**

To view your bot's live logs, run:

```bash
gcloud run services logs --stream <image-name> --region=us-central1
```

## **Method 2: Google Compute Engine (VM)**

This method gives you a full Linux virtual machine to run your bot.

### **Step 1: Create the VM Instance**

1.  Navigate to the **Compute Engine -> VM instances** page in your Google Cloud Console.
2.  Click **Create Instance**.
3.  Configure the instance with the following settings to stay in the free tier:
    *   **Name:** `discord-bot-vm`
    *   **Region:** `us-central1` (Iowa)
    *   **Zone:** Any `us-central1` zone
    *   **Machine configuration:**
        *   Series: **E2**
        *   Machine type: **e2-micro**
    *   **Boot disk:**
        *   Operating System: **Ubuntu**
        *   Version: **Ubuntu 22.04 LTS** (or newer LTS)
    *   **Firewall:** Check both **Allow HTTP traffic** and **Allow HTTPS traffic**.
4.  Click **Create**.

### **Step 2: Connect and Set Up the Server**

1.  From the VM instances list, find your new VM and click the **SSH** button to open a terminal in your browser.
2.  In the VM's terminal, update the system and install required software:
    ```bash
    sudo apt update && sudo apt upgrade -y
    sudo apt install python3 python3-pip git -y
    ```

### **Step 3: Deploy and Run the Bot**

1.  **Clone your repository:**
    ```bash
    git clone https://github.com/Dood345/Doods-Discord-Bot.git
    ```

2.  **Install dependencies:**
    ```bash
    cd Doods-Discord-Bot
    pip3 install -r requirements.txt
    ```

3.  **Create a background service:** We will use `systemd` to ensure your bot runs 24/7 and restarts automatically if it crashes.
    *   Create a new service file:
        ```bash
        sudo nano /etc/systemd/system/discord-bot.service
        ```

    *   Paste the following configuration. **Replace the placeholder tokens with your actual secrets.**
        ```ini
        [Unit]
        Description=Doods Discord Bot
        After=network.target

        [Service]
        User=<your_gcp_username>
        Group=<your_gcp_username>
        WorkingDirectory=/home/<your_gcp_username>/Doods-Discord-Bot
        ExecStart=/usr/bin/python3 /home/<your_gcp_username>/Doods-Discord-Bot/discord_bot/main.py
        Environment="DISCORD_TOKEN=YOUR_DISCORD_TOKEN"
        Environment="GEMINI_API_KEY=YOUR_GEMINI_KEY"
        Restart=always

        [Install]
        WantedBy=multi-user.target
        ```
        *(Note: Your GCP username is the part before the @ in the SSH terminal prompt)*
    *   Save and exit nano: Press `Ctrl+X`, then `Y`, then `Enter`.

### **Step 4: Start and Manage the Service**

1.  **Reload systemd to recognize your new file:**
    ```bash
    sudo systemctl daemon-reload
    ```

2.  **Enable the service to start automatically on boot:**
    ```bash
    sudo systemctl enable discord-bot.service
    ```

3.  **Start the bot now:**
    ```bash
    sudo systemctl start discord-bot.service
    ```

4.  **Check the status and logs:**
    *   Check status:
        ```bash
        sudo systemctl status discord-bot.service
        ```
    *   View live logs:
        ```bash
        journalctl -u discord-bot.service -f
        ```