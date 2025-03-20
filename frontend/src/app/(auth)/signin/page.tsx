"use client"

import { useForm, type SubmitHandler } from "react-hook-form";
import { login } from "@/lib/auth/actions";
import type { BodyLoginLoginAccessToken as AccessToken } from "@/client/types.gen"
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function SignIn() {
  const router = useRouter()
  
  const {
    register,
    handleSubmit,
    formState: { isSubmitting, errors },
  } = useForm<AccessToken>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      username: "",
      password: "",
    },
  })

  const onSubmit: SubmitHandler<AccessToken> = async (data) => {
    if (isSubmitting) return

    try {
      const res = await login(data)
      console.log(res)
      router.push("/")
    } catch (error) {
      console.error("Login error:", error)
      // error is handled by useAuth hook
    }
  }

  return (
    <div className="max-w-md mx-auto">
      <div className="mb-10">
        <h1 className="text-4xl font-bold">Sign in to your account</h1>
      </div>
      {/* Form */}
      <form onSubmit={handleSubmit(onSubmit)}>
        <div className="space-y-4">
          <div>
            <label
              className="mb-1 block text-sm font-medium text-gray-700"
              htmlFor="email"
            >
              Email
            </label>
            <input
              id="email"
              className={`form-input w-full py-2 ${errors.username ? 'border-red-500' : ''}`}
              type="email"
              placeholder="corybarker@email.com"
              {...register("username", { 
                required: "Email is required",
                pattern: {
                  value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                  message: "Invalid email address"
                }
              })}
            />
            {errors.username && (
              <p className="mt-1 text-sm text-red-600">{errors.username.message}</p>
            )}
          </div>
          <div>
            <label
              className="mb-1 block text-sm font-medium text-gray-700"
              htmlFor="password"
            >
              Password
            </label>
            <input
              id="password"
              className={`form-input w-full py-2 ${errors.password ? 'border-red-500' : ''}`}
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              {...register("password", { 
                required: "Password is required",
                minLength: {
                  value: 6,
                  message: "Password must be at least 6 characters"
                }
              })}
            />
            {errors.password && (
              <p className="mt-1 text-sm text-red-600">{errors.password.message}</p>
            )}
          </div>
        </div>
        <div className="mt-6">
          <button 
            type="submit" 
            className="btn w-full bg-linear-to-t from-blue-600 to-blue-500 bg-[length:100%_100%] bg-[bottom] text-white shadow-sm hover:bg-[length:100%_150%]"
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Signing in...' : 'Sign In'}
          </button>
        </div>
      </form>
      {/* Bottom link */}
      <div className="mt-6 text-center">
        <Link
          className="text-sm text-gray-700 underline hover:no-underline"
          href="/reset-password"
        >
          Forgot password
        </Link>
        <Link
          className="ml-2 text-sm text-gray-700 underline hover:no-underline"
          href="/signup"
        >
          Don&apos;t have an account? Sign up
        </Link>
      </div>
    </div>
  );
}