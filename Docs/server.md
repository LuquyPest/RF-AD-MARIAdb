# Server install

# **Summary**
- [The Active Directory part](./server.md/#the-active-directory-part)
    - [1. Modify the LDAP Schema](./server.md/#1-modify-the-ldap-schema)  
    - [2. Create an LDAP User for Sync](./server.md/#2-create-an-ldap-user-for-sync)
- [The Linux Part](./server.md/#the-linux-part)
    - [3. Clone the Repository](./server.md/#3-clone-the-repository)
    - [4. Create the .env File](./server.md/#4-create-the-env-file)
    - [5. Build and Run the Docker Container](./server.md/#5-build-and-run-the-docker-container)

# The Active Directory part

## 1. Modify the LDAP Schema

To add the `rFIDUID` attribute to your LDAP schema, follow these steps:

### Open PowerShell as Administrator

1. **Open PowerShell as Administrator**: This is required to make changes to the LDAP schema.

### Add the `rFIDUID` Attribute

2. **Add the `rFIDUID` Attribute**: Use the following PowerShell commands to add the `rFIDUID` attribute to the LDAP schema.

   ```powershell
   Import-Module ActiveDirectory

   # Define the new attribute
   $attribute = New-Object PSObject -Property @{
       lDAPDisplayName = "rFIDUID"
       adminDescription = "RFID UID"
       attributeSyntax = "2.5.5.12"
       oMSyntax = 64
       isSingleValued = $true
   }

   # Add the new attribute to the schema
   New-ADObject -Name "rFIDUID" -Type "attributeSchema" -OtherAttributes $attribute

3. **Add the Attribute to a Class**: Update the user class to include the `rFIDUID` attribute.
    ```powershell
    # Find the user class
    $userClass = Get-ADObject -LDAPFilter "(cn=user)" -SearchBase "CN=Schema,CN=Configuration,DC=your-domain,DC=com" -SearchScope Base

    # Add the new attribute to the user class
    Set-ADObject -Identity $userClass -Add @{mayContain="rFIDUID"}
    ```

## 2. Create an LDAP User for Sync
Create a dedicated LDAP user for synchronizing data:  
⚠️ Do not forget to replace the domain by yours and the password by a strong one.
```powershell
    New-ADUser -Name "RO.RF-AD" ` #You can change this if you want 
        -GivenName "ReadOnly" `
        -Surname "AD" `
        -UserPrincipalName "RO.RF-AD@your-domain.com" `
        -Path "OU=Users,DC=your-domain,DC=com" `
        -AccountPassword (ConvertTo-SecureString -AsPlainText "[YOUR PASSWORD]" -Force) `
        -Enabled $true

    # Grant read permissions
    $ldapUser = Get-ADUser -Identity "RO.RF-AD"
    Add-ADPermission -Identity "OU=Users,DC=your-domain,DC=com" -User $ldapUser -AccessRights ReadProperty
```

# The Linux Part

For this part you'll need docker, you can frollow this tutorial to install it proprely  
➡️ [Official Guide to install docker](https://docs.docker.com/engine/install/)  
⚠️ I cannot guarantee the accuracy of the information contained in this guide. ⚠️
## 3. Clone the Repository

```bash
git clone https://github.com/jeanGaston/RF-AD.git
```
Then navigate into the server folder
```bash
cd ./RD-AD/Server
```
## 4. Create the `.env` File

Create a `.env` file in the [server directory](../Server/) with the following content:

```
LDAPUSER=[The user you have created earlier] 
LDAPPASS=[The password you have created earlier]
LDAP_SERVER=ldap://[The IP of your DC] 
DOOR_ACCESS_GROUPS_DN=[The DN of the OU containing groups assiociated with doors]
USERS_DN=[The DN of the OU containing the users]
DBFILE=/db/data.db #You can change this if you want
WebServerPORT=5000 #You can change this if you want 
```
⚠️ **IF YOU CHANGE THE WEB SERVER PORT** ⚠️  
You'll need to change it in the [reader code](../Client/main.py) and in the [docker-compose.yml](../Server/docker-compose.yml) and [dockerfile](../Server/Dockerfile)

## 5. Build and Run the Docker Container

Execute this code 
```bash
docker compose build --no-cache
docker compose up -d
```

