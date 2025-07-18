## How to run this Terraform

1. **Install Terraform**

   * Download from [https://www.terraform.io/downloads.html](https://www.terraform.io/downloads.html)
   * Unzip and move the `terraform` binary into your `PATH` (e.g. `/usr/local/bin`).

2. **Create a working directory**

   ```bash
   mkdir hetzner-api && cd hetzner-api
   # save the above as main.tf in this directory
   ```

3. **Provide your Hetzner token & SSH key**
   Create a file named `terraform.tfvars` in the same folder:

   ```hcl
   hcloud_token = "YOUR-HCLOUD-API-TOKEN"
   # adjust the path if your public key is elsewhere:
   ssh_key_path = "/home/youruser/.ssh/id_rsa.pub"
   ```

4. **Initialize Terraform**

   ```bash
   terraform init
   ```

   This downloads the Hetzner provider.

5. **Inspect the plan**

   ```bash
   terraform plan
   ```

   * Verify it will create a firewall, SSH key, and one server.
   * **No resources are created yet**.

6. **Apply the plan**

   ```bash
   terraform apply
   ```

   * Type `yes` when prompted.
   * Terraform will provision the server and run the cloud‑init script.

7. **Get your server’s IP**
   After apply completes, you’ll see:

   ```
   Outputs:

   api_server_ip = 123.123.123.123
   ```

   That’s the public address of your FastAPI service.

8. **Test your API**

   ```bash
   curl http://123.123.123.123/your‑endpoint
   ```

   Replace `/your-endpoint` with any route you defined (e.g. `/urgent`).

9. **SSH in (optional)**

   ```bash
   ssh root@123.123.123.123
   ```

   Your SSH key grants you access.

---

### Notes & next steps

* **Customizing**

  * Change `server_type` if you need more CPU/RAM.
  * Update the `git clone` URL to point at your actual repo.
  * If you serve on port 443, add SSL (e.g. via Certbot) in your cloud‑init.

* **Destroying resources**
  When you’re done:

  ```bash
  terraform destroy
  ```

  This tears down the server, firewall, and SSH key.

That’s it — you’ve got a repeatable Terraform workflow to host your API on Hetzner!
