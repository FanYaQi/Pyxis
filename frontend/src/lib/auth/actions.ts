import { client } from "@/client/client.gen"
import { LoginService } from "@/client/sdk.gen"

import {
  type BodyLoginLoginAccessToken as AccessToken,
} from "@/client/types.gen"


export const login = async (data: AccessToken) => {
  const response = await LoginService.loginAccessToken({
    client: client,
    body: data,
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
  })
  return response
}
