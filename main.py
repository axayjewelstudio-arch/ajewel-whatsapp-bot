from dotenv import load_dotenv
import os

load_dotenv()

token = os.getenv("META_SYSTEM_USER_TOKEN")
print(token)
```

---

### Step 4: `.gitignore` me `.env` add karo ⚠️

Ye **sabse important step** hai — `.env` ko GitHub par kabhi mat daalo:
```
# .gitignore file me ye line add karo
.env
