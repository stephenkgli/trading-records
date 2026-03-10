/**
 * Tradovate API 免费访问测试脚本
 *
 * 测试目标：验证是否可以不付 $25/月 API 订阅，
 * 仅用用户名+密码获取 access token 并读取交易记录（fills）。
 *
 * 用法：
 *   npx tsx scripts/test-tradovate-api.ts
 *
 * 首次运行前，请设置环境变量：
 *   export TRADOVATE_USERNAME="你的Tradovate用户名"
 *   export TRADOVATE_PASSWORD="你的Tradovate密码"
 *
 * 可选环境变量：
 *   TRADOVATE_ENV=live|demo    (默认 live)
 *   TRADOVATE_CID=xxx          (可选，4位数字)
 *   TRADOVATE_SECRET=xxx       (可选)
 */

// ============================================================
// 配置
// ============================================================

const ENV = (process.env.TRADOVATE_ENV || "live") as "live" | "demo";
const USERNAME = process.env.TRADOVATE_USERNAME;
const PASSWORD = process.env.TRADOVATE_PASSWORD;
const CID = process.env.TRADOVATE_CID;
const SECRET = process.env.TRADOVATE_SECRET;

// 固定 deviceId，避免每次触发 2FA 设备审批
const DEVICE_ID = "d8b5a0f3-7c2e-4e1a-9f6d-3a8b7c5e2d10";

const BASE_URL =
  ENV === "live"
    ? "https://live.tradovateapi.com/v1"
    : "https://demo.tradovateapi.com/v1";

// ============================================================
// 工具函数
// ============================================================

function log(label: string, data: unknown) {
  console.log(`\n${"=".repeat(60)}`);
  console.log(`  ${label}`);
  console.log("=".repeat(60));
  if (typeof data === "string") {
    console.log(data);
  } else {
    console.log(JSON.stringify(data, null, 2));
  }
}

// ============================================================
// Step 1: 获取 Access Token
// ============================================================

async function getAccessToken(): Promise<string | null> {
  log("Step 1: 请求 Access Token", {
    url: `${BASE_URL}/auth/accesstokenrequest`,
    env: ENV,
    username: USERNAME,
    hasCid: !!CID,
    hasSecret: !!SECRET,
  });

  const body: Record<string, string> = {
    name: USERNAME!,
    password: PASSWORD!,
    appId: "TradingRecords",
    appVersion: "1.0",
    deviceId: DEVICE_ID,
  };

  // 如果提供了 CID 和 Secret，加入请求体
  if (CID) body.cid = CID;
  if (SECRET) body.sec = SECRET;

  const res = await fetch(`${BASE_URL}/auth/accesstokenrequest`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(body),
  });

  const data = await res.json();

  if (!res.ok) {
    log("认证失败 (HTTP Error)", { status: res.status, data });
    return null;
  }

  // 检查 p-ticket（2FA 设备审批）
  if (data["p-ticket"]) {
    log("需要设备审批 (p-ticket)", {
      message:
        "首次从新设备登录，Tradovate 需要设备审批。" +
        "请检查你的注册邮箱，点击设备批准链接后重新运行此脚本。",
      "p-ticket": data["p-ticket"],
      raw: data,
    });
    return null;
  }

  if (!data.accessToken) {
    log("认证失败 (无 Token)", data);
    return null;
  }

  log("认证成功!", {
    tokenPreview: data.accessToken.substring(0, 30) + "...",
    expirationTime: data.expirationTime,
    userId: data.userId,
  });

  return data.accessToken;
}

// ============================================================
// Step 2: 获取账户列表
// ============================================================

async function getAccounts(token: string) {
  log("Step 2: 获取账户列表", `GET ${BASE_URL}/account/list`);

  const res = await fetch(`${BASE_URL}/account/list`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  const data = await res.json();

  if (!res.ok) {
    log("获取账户失败", { status: res.status, data });
    return null;
  }

  log(
    "账户列表",
    Array.isArray(data)
      ? data.map((a: Record<string, unknown>) => ({
          id: a.id,
          name: a.name,
          active: a.active,
        }))
      : data
  );

  return data;
}

// ============================================================
// Step 3: 获取成交记录 (Fills)
// ============================================================

async function getFills(token: string) {
  log("Step 3: 获取成交记录 (Fill List)", `GET ${BASE_URL}/fill/list`);

  const res = await fetch(`${BASE_URL}/fill/list`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  const data = await res.json();

  if (!res.ok) {
    log("获取 Fill 失败", { status: res.status, data });
    return null;
  }

  if (Array.isArray(data)) {
    log(`获取到 ${data.length} 条成交记录`, data.slice(0, 5));
    if (data.length > 5) {
      console.log(`  ... 还有 ${data.length - 5} 条记录未显示`);
    }
  } else {
    log("Fill 数据", data);
  }

  return data;
}

// ============================================================
// Step 4: 获取订单列表 (Orders)
// ============================================================

async function getOrders(token: string) {
  log("Step 4: 获取订单列表 (Order List)", `GET ${BASE_URL}/order/list`);

  const res = await fetch(`${BASE_URL}/order/list`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  const data = await res.json();

  if (!res.ok) {
    log("获取 Order 失败", { status: res.status, data });
    return null;
  }

  if (Array.isArray(data)) {
    log(`获取到 ${data.length} 条订单记录`, data.slice(0, 5));
    if (data.length > 5) {
      console.log(`  ... 还有 ${data.length - 5} 条记录未显示`);
    }
  } else {
    log("Order 数据", data);
  }

  return data;
}

// ============================================================
// Step 5: 获取持仓列表 (Positions)
// ============================================================

async function getPositions(token: string) {
  log("Step 5: 获取持仓列表 (Position List)", `GET ${BASE_URL}/position/list`);

  const res = await fetch(`${BASE_URL}/position/list`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  const data = await res.json();

  if (!res.ok) {
    log("获取 Position 失败", { status: res.status, data });
    return null;
  }

  log("持仓数据", data);
  return data;
}

// ============================================================
// 主流程
// ============================================================

async function main() {
  console.log("\n🔍 Tradovate API 免费访问测试");
  console.log(`   环境: ${ENV}`);
  console.log(`   Base URL: ${BASE_URL}`);
  console.log(`   Device ID: ${DEVICE_ID}`);

  // 检查凭据
  if (!USERNAME || !PASSWORD) {
    console.error(
      "\n❌ 请先设置环境变量:\n" +
        "   export TRADOVATE_USERNAME='你的用户名'\n" +
        "   export TRADOVATE_PASSWORD='你的密码'\n"
    );
    process.exit(1);
  }

  // Step 1: 获取 Token
  const token = await getAccessToken();
  if (!token) {
    console.log("\n❌ 无法获取 Access Token，测试终止。");
    process.exit(1);
  }

  // Step 2-5: 并行请求所有数据端点
  const results = await Promise.allSettled([
    getAccounts(token),
    getFills(token),
    getOrders(token),
    getPositions(token),
  ]);

  // 汇总结果
  log("测试结果汇总", {
    认证: "✅ 成功",
    账户列表:
      results[0].status === "fulfilled" && results[0].value
        ? "✅ 成功"
        : "❌ 失败",
    成交记录:
      results[1].status === "fulfilled" && results[1].value
        ? "✅ 成功"
        : "❌ 失败",
    订单列表:
      results[2].status === "fulfilled" && results[2].value
        ? "✅ 成功"
        : "❌ 失败",
    持仓列表:
      results[3].status === "fulfilled" && results[3].value
        ? "✅ 成功"
        : "❌ 失败",
  });

  console.log(
    "\n如果以上端点全部成功，说明 Tradovate API 可以免费读取交易数据！"
  );
  console.log("你可以将此方案集成到 trading-records 应用中。\n");
}

main().catch(console.error);
