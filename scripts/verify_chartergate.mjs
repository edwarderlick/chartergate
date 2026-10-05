import fs from "node:fs";
import crypto from "node:crypto";
import { config } from "dotenv";
import { createAccount, createClient, chains } from "genlayer-js";

config();

const studioDev = {
  ...chains.studionet,
  id: 61997,
  rpcUrls: {
    default: { http: ["https://studio-dev.genlayer.com/api"] },
  },
};

function sha256(text) {
  return crypto.createHash("sha256").update(text, "utf8").digest("hex");
}

function jsonSafe(value) {
  return JSON.parse(
    JSON.stringify(value, (_, item) =>
      typeof item === "bigint" ? item.toString() : item,
    ),
  );
}

function originalRejectedSource(source) {
  const callback = `
    @gl.public.write.payable
    def __on_errored_message__(self) -> None:
        failed_value = int(gl.message.value)
        if failed_value <= 0:
            return
`;

  return source.replace(
    "    @gl.public.write\n    def withdraw_treasury",
    `${callback}\n    @gl.public.write\n    def withdraw_treasury`,
  );
}

async function captureSchema(client, code) {
  try {
    return {
      ok: true,
      schema: await client.getContractSchemaForCode(code),
    };
  } catch (error) {
    return {
      ok: false,
      error: {
        name: error?.name,
        message: error?.message,
        details: error?.details,
        shortMessage: error?.shortMessage,
      },
    };
  }
}

async function main() {
  const privateKey = process.env.PRIVATE_KEY;
  if (!privateKey) {
    throw new Error("PRIVATE_KEY is required for the deployment step");
  }

  const account = createAccount(privateKey);
  const client = createClient({ chain: studioDev, account });
  const code = fs.readFileSync("contracts/charter_gate.py", "utf8");
  const sponsor = account.address;
  const sunset = Math.floor(Date.now() / 1000) + 86400 * 365;
  const codeHashIndex = process.argv.indexOf("--code-hash");

  if (codeHashIndex !== -1) {
    const address = process.argv[codeHashIndex + 1];
    if (!address) {
      throw new Error("--code-hash requires a contract address");
    }
    const evidencePath = "deploy/chartergate_validation.json";
    const evidence = fs.existsSync(evidencePath)
      ? JSON.parse(fs.readFileSync(evidencePath, "utf8"))
      : {};
    const receipt = fs.existsSync("deploy/receipt.json")
      ? JSON.parse(fs.readFileSync("deploy/receipt.json", "utf8"))
      : {};
    const remoteCode = await client.getContractCode(address);
    evidence.deployment = {
      ...(evidence.deployment || {}),
      address,
      txHash: receipt.deploy_tx,
      receipt,
    };
    evidence.codeHashComparison = {
      localSha256: sha256(code),
      remoteSha256: sha256(remoteCode),
      match: sha256(code) === sha256(remoteCode),
    };
    fs.mkdirSync("deploy", { recursive: true });
    fs.writeFileSync(evidencePath, `${JSON.stringify(evidence, null, 2)}\n`);
    console.log(JSON.stringify(evidence.codeHashComparison, null, 2));
    return;
  }

  const originalValidation = await captureSchema(client, originalRejectedSource(code));
  const finalValidation = await captureSchema(client, code);
  if (!finalValidation.ok) {
    throw new Error(
      `Final schema validation failed: ${JSON.stringify(finalValidation.error)}`,
    );
  }

  const evidence = {
    checkedAt: new Date().toISOString(),
    network: "studio-dev",
    runnerDepends:
      "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng",
    runnerStdlib:
      "py-lib-genlayer-std:kzr02ndm9et4qkmbqpq5djjt5sme2yt76n7sz1qbzax0knt6mam0",
    unsupportedCallbackFinding:
      "The pinned SDK bootloader dispatches __receive__ and __handle_undefined_method__ only; it has no __on_errored_message__ branch. The pinned schema generator rejects public method names beginning with double underscores.",
    originalValidation,
    finalValidation: {
      ok: true,
      methodNames: Object.keys(finalValidation.schema.methods),
      schema: finalValidation.schema,
    },
    deployment: null,
    codeHashComparison: null,
  };

  fs.mkdirSync("deploy", { recursive: true });
  fs.writeFileSync(
    "deploy/chartergate_validation.json",
    `${JSON.stringify(evidence, null, 2)}\n`,
  );

  if (process.argv.includes("--schema-only")) {
    console.log(JSON.stringify(evidence, null, 2));
    return;
  }

  try {
    await client.initializeConsensusSmartContract?.();
    const txHash = await client.deployContract({
      code,
      args: [
        sponsor,
        "CharterGate deployment validating the Steward schema correction.",
        sponsor,
        1,
        1,
        sunset,
      ],
    });

    const receipt = await client.waitForTransactionReceipt({
      hash: txHash,
      status: "ACCEPTED",
      retries: 200,
    });
    const address =
      receipt.contractAddress ||
      receipt.data?.contract_address ||
      receipt.txDataDecoded?.contractAddress;
    const remoteCode = await client.getContractCode(address);

    evidence.deployment = {
      txHash,
      receipt: jsonSafe(receipt),
      address,
    };
    evidence.codeHashComparison = {
      localSha256: sha256(code),
      remoteSha256: sha256(remoteCode),
      match: sha256(code) === sha256(remoteCode),
    };
  } catch (error) {
    evidence.deployment = {
      error: {
        name: error?.name,
        message: error?.message,
        details: error?.details,
        shortMessage: error?.shortMessage,
      },
    };
  }

  fs.writeFileSync(
    "deploy/chartergate_validation.json",
    `${JSON.stringify(evidence, null, 2)}\n`,
  );
  console.log(JSON.stringify(evidence, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
