'use client';

import * as React from 'react';
import { useState, useEffect, useCallback } from 'react';
import { X, Mail, Lock, Eye, EyeOff, Check } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { InputOTP, InputOTPGroup, InputOTPSlot } from '@/components/ui/input-otp';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import axios from 'axios';
import { API_ENDPOINTS } from '@/services/endpoints';
import Button from '@/app/(dashboard)/components/Button';
import { cn } from '@/lib/utils';

// Types for API responses
interface ApiResponse {
  success: boolean;
  message: string;
  data?: any;
}

// Configuration for API endpoints
interface ApiConfig {
  sendOtpEndpoint: string;
  verifyOtpEndpoint: string;
  resetPasswordEndpoint: string;
}

// Component props
interface OtpPasswordResetDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// Dialog stages
enum DialogStage {
  EMAIL = 'email',
  OTP = 'otp',
  PASSWORD = 'password',
}

// Password validation rules
interface PasswordValidation {
  minLength: boolean;
  hasUppercase: boolean;
  hasLowercase: boolean;
  hasNumber: boolean;
  hasSpecialChar: boolean;
  passwordsMatch: boolean;
}

export function OtpPasswordResetDialog({ open, onOpenChange }: OtpPasswordResetDialogProps) {
  // State management
  const [stage, setStage] = useState<DialogStage>(DialogStage.EMAIL);
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [resendLoading, setResendLoading] = useState(false);
  const [timer, setTimer] = useState(0);
  const [passwordValidation, setPasswordValidation] = useState<PasswordValidation>({
    minLength: false,
    hasUppercase: false,
    hasLowercase: false,
    hasNumber: false,
    hasSpecialChar: false,
    passwordsMatch: false,
  });

  const timerIntervalRef = React.useRef<NodeJS.Timeout | null>(null);

  // Password validation functions
  const validatePassword = (password: string, confirmPassword: string = '') => {
    const validation: PasswordValidation = {
      minLength: password.length >= 8,
      hasUppercase: /[A-Z]/.test(password),
      hasLowercase: /[a-z]/.test(password),
      hasNumber: /[0-9]/.test(password),
      hasSpecialChar: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password),
      passwordsMatch: password === confirmPassword && password.length > 0,
    };
    setPasswordValidation(validation);
    return validation;
  };

  // Check if all password requirements are met
  const isPasswordValid = () => {
    const { passwordsMatch, ...otherValidations } = passwordValidation;
    return Object.values(otherValidations).every(Boolean) && passwordsMatch;
  };

  // Reset form when dialog closes
  const handleDialogChange = (open: boolean) => {
    if (!open && !loading) {
      resetForm();
    }
    onOpenChange(open);
  };

  // Reset all form data
  const resetForm = () => {
    setStage(DialogStage.EMAIL);
    setEmail('');
    setOtp('');
    setPassword('');
    setConfirmPassword('');
    setErrors({});
    setLoading(false);
    setShowPassword(false);
    setShowConfirmPassword(false);
    setPasswordValidation({
      minLength: false,
      hasUppercase: false,
      hasLowercase: false,
      hasNumber: false,
      hasSpecialChar: false,
      passwordsMatch: false,
    });
  };

  // Validate email format
  const validateEmail = (email: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  // Clear specific error
  const clearError = (field: string) => {
    setErrors((prev) => {
      const newErrors = { ...prev };
      delete newErrors[field];
      return newErrors;
    });
  };

  // API call to send OTP
  const handleSendOtp = async () => {
    setErrors({});

    if (!email.trim()) {
      setErrors({ email: 'Email is required' });
      return;
    }

    if (!validateEmail(email)) {
      setErrors({ email: 'Please enter a valid email address' });
      return;
    }

    setLoading(true);

    try {
      const response = await axios.post(API_ENDPOINTS.SEND_VERIFICATION_OTP, {
        email,
        purpose: 'password_reset',
      });

      const data: ApiResponse = response.data;

      setStage(DialogStage.OTP);
      setResendLoading(true);
      startTimer();
      toast.success(`A 6-digit OTP has been sent to your email`);
    } catch (error: any) {
      setErrors({ email: error?.response?.data?.detail || 'something, went wrong' });
    } finally {
      setLoading(false);
    }
  };

  // API call to verify OTP
  const handleVerifyOtp = async () => {
    setErrors({});

    if (otp.length !== 6) {
      setErrors({ otp: 'Please enter a valid 6-digit OTP' });
      return;
    }

    setLoading(true);

    try {
      const response = await axios.post(API_ENDPOINTS.VERIFY_OTP, {
        email,
        otp,
      });

      const data: ApiResponse = response.data;

      setStage(DialogStage.PASSWORD);
      toast.success('Please enter your new password');
    } catch (error: any) {
      setErrors({ otp: error.response?.data?.detail || 'Invalid OTP' });
    } finally {
      setLoading(false);
    }
  };

  // API call to reset password
  const handleResetPassword = async () => {
    setErrors({});

    if (!isPasswordValid()) {
      setErrors({ password: 'Please ensure all password requirements are met' });
      return;
    }

    setLoading(true);

    try {
      const response = await axios.post(API_ENDPOINTS.RESET_PASSWORD, {
        email,
        otp,
        new_password: password,
      });

      const data: ApiResponse = response.data;

      if (data.success) {
        toast.success('Your password has been successfully updated');
        onOpenChange(false);
        resetForm();
      } else {
        setErrors({ password: data.message || 'Failed to update password' });
      }
    } catch (error: any) {
      setErrors({ password: error?.response?.data?.detail || 'something, went wrong' });
    } finally {
      setLoading(false);
    }
  };

  // Handle OTP input change
  const handleOtpChange = (value: string) => {
    setOtp(value);
    clearError('otp');
  };

  // Handle password input change
  const handlePasswordChange = (value: string) => {
    setPassword(value);
    validatePassword(value, confirmPassword);
    clearError('password');
  };

  // Handle confirm password input change
  const handleConfirmPasswordChange = (value: string) => {
    setConfirmPassword(value);
    validatePassword(password, value);
    clearError('confirmPassword');
  };

  // Validation indicator component
  const ValidationIndicator = ({ isValid, text }: { isValid: boolean; text: string }) => (
    <div className="flex items-center gap-2">
      {isValid ? (
        <Check className="w-4 h-4 text-green-500" />
      ) : (
        <X className="w-4 h-4 text-red-500" />
      )}
      <span className={cn('text-sm', isValid ? 'text-green-600' : 'text-red-600')}>{text}</span>
    </div>
  );

  // Render email stage
  const renderEmailStage = () => (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="email">Email Address</Label>
        <div className="relative">
          <Mail className="absolute left-3 top-3 size-5 text-muted-foreground" />
          <input
            id="email"
            type="email"
            placeholder="Enter your email address"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              clearError('email');
            }}
            className={`pl-10 block w-full px-3 py-3 bg-[var(--primary-chart-bg)] border ${
              errors.email ? 'border-red-500' : 'border-primary-100'
            } rounded-md shadow-sm placeholder-neutral-150 focus:outline-none focus:ring-2 focus:ring-[#4B9770] sm:text-sm transitiona-ll duration-200`}
            disabled={loading}
            autoComplete="email"
          />
        </div>
        {errors.email && (
          <p className="text-sm text-destructive" role="alert">
            {errors.email}
          </p>
        )}
      </div>
      <Button onClick={handleSendOtp} className="w-full bg-[#4B9770]" disabled={loading}>
        {loading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Sending OTP...
          </>
        ) : (
          'Get OTP'
        )}
      </Button>
    </div>
  );

  // Render OTP stage
  const renderOtpStage = () => (
    <div className="space-y-4">
      <div className="space-y-8">
        <p className="text-sm text-muted-foreground w-full">
          We've sent a verification code to {email}
        </p>
        <div className="flex justify-center">
          <InputOTP maxLength={6} value={otp} onChange={handleOtpChange} disabled={loading}>
            <InputOTPGroup className="flex gap-x-3">
              {[0, 1, 2, 3, 4, 5].map((i) => (
                <InputOTPSlot key={i} index={i} />
              ))}
            </InputOTPGroup>
          </InputOTP>
        </div>
        {errors.otp && (
          <p className="text-sm text-destructive text-center" role="alert">
            {errors.otp}
          </p>
        )}
      </div>
      <div className="text-center">
        {timer > 0 ? (
          <span className="text-sm text-primary-main">Resend OTP in {timer} sec</span>
        ) : (
          <button
            onClick={handleResendOtp}
            disabled={resendLoading}
            className="text-sm underline text-primary-main"
          >
            {resendLoading ? 'Resending...' : 'Resend OTP'}
          </button>
        )}
      </div>
      <Button
        variant="primary"
        onClick={handleVerifyOtp}
        className="w-full"
        disabled={loading || otp.length !== 6}
      >
        {loading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Verifying OTP...
          </>
        ) : (
          'Verify OTP'
        )}
      </Button>
    </div>
  );

  // Render password stage
  const renderPasswordStage = () => (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="password">New Password</Label>
        <div className="relative">
          <Lock className="absolute left-3 top-3 size-5 text-muted-foreground" />
          <input
            id="password"
            type={showPassword ? 'text' : 'password'}
            placeholder="Enter new password"
            value={password}
            onChange={(e) => handlePasswordChange(e.target.value)}
            className={`pl-10 block w-full px-3 py-3 bg-[var(--primary-chart-bg)] border ${
              errors.password ? 'border-red-500 focus:ring-red-500 ' : 'border-primary-100'
            } rounded-md shadow-sm placeholder-neutral-150 focus:outline-none focus:ring-2 focus:ring-[#4B9770] sm:text-sm transition-all duration-200`}
            disabled={loading}
            autoComplete="new-password"
          />
          <button
            type="button"
            className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
            onClick={() => setShowPassword(!showPassword)}
            disabled={loading}
            aria-label={showPassword ? 'Hide password' : 'Show password'}
          >
            {showPassword ? (
              <EyeOff className="size-5 text-muted-foreground" />
            ) : (
              <Eye className="size-5 text-muted-foreground" />
            )}
          </button>
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="confirmPassword">Confirm Password</Label>
        <div className="relative">
          <Lock className="absolute left-3 top-3 size-5 text-muted-foreground" />
          <input
            id="confirmPassword"
            type={showConfirmPassword ? 'text' : 'password'}
            placeholder="Confirm new password"
            value={confirmPassword}
            onChange={(e) => handleConfirmPasswordChange(e.target.value)}
            className={`pl-10 block w-full px-3 py-3 bg-[var(--primary-chart-bg)] border ${
              errors.confirmPassword ? 'border-red-500' : 'border-primary-100'
            } rounded-md shadow-sm placeholder-neutral-150 focus:outline-none focus:ring-2 focus:ring-[#4B9770] sm:text-sm transitiona-ll duration-200`}
            disabled={loading}
            autoComplete="new-password"
          />
          <button
            type="button"
            className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
            onClick={() => setShowConfirmPassword(!showConfirmPassword)}
            disabled={loading}
            aria-label={showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
          >
            {showConfirmPassword ? (
              <EyeOff className="size-5 text-muted-foreground" />
            ) : (
              <Eye className="size-5 text-muted-foreground" />
            )}
          </button>
        </div>
      </div>

      {/* Password Validation Rules */}
      <div className="space-y-2">
        <ValidationIndicator
          isValid={passwordValidation.minLength}
          text="Be at least 8 characters long."
        />
        <ValidationIndicator
          isValid={passwordValidation.hasUppercase}
          text="Include at least one uppercase letter (A-Z)."
        />
        <ValidationIndicator
          isValid={passwordValidation.hasLowercase}
          text="Include at least one lowercase letter (a-z)."
        />
        <ValidationIndicator
          isValid={passwordValidation.hasNumber}
          text="Include at least one number (0-9)."
        />
        <ValidationIndicator
          isValid={passwordValidation.hasSpecialChar}
          text="Include at least one special character (e.g. !@#$%)."
        />
        <ValidationIndicator isValid={passwordValidation.passwordsMatch} text="Passwords match." />
      </div>

      {errors.password && (
        <p className="text-sm text-destructive" role="alert">
          {errors.password}
        </p>
      )}

      <Button
        onClick={handleResetPassword}
        className="w-full"
        disabled={loading || !isPasswordValid()}
        variant="primary"
      >
        {loading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Updating Password...
          </>
        ) : (
          'Continue'
        )}
      </Button>
    </div>
  );

  // Get dialog title based on current stage
  const getDialogTitle = () => {
    switch (stage) {
      case DialogStage.EMAIL:
        return 'Reset Password';
      case DialogStage.OTP:
        return 'Verify OTP';
      case DialogStage.PASSWORD:
        return 'Set New Password';
      default:
        return 'Reset Password';
    }
  };

  // Get dialog description based on current stage
  const getDialogDescription = () => {
    switch (stage) {
      case DialogStage.EMAIL:
        return 'Enter your email address to receive a verification code';
      case DialogStage.OTP:
        return 'Enter the 6-digit code sent to your email';
      case DialogStage.PASSWORD:
        return 'Create a new password for your account';
      default:
        return '';
    }
  };

  const startTimer = useCallback(() => {
    setTimer(30);
    // Clear any existing interval before starting a new one
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
    }
    timerIntervalRef.current = setInterval(() => {
      setTimer((prev) => {
        if (prev <= 1) {
          clearInterval(timerIntervalRef.current!);
          setResendLoading(false);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }, [timer]);

  const handleResendOtp = async () => {
    setResendLoading(true);
    setErrors({});
    try {
      await axios.post(API_ENDPOINTS.SEND_VERIFICATION_OTP, {
        email,
        purpose: 'password_reset',
      });
      setOtp('');
      startTimer();
      toast.success(`A 6-digit OTP has been sent to your email`);
    } catch (error: any) {
      toast.error(
        error?.response?.data?.detail || 'An unexpected error occured, Please try again later',
      );
      setTimer(0);
    } finally {
      setResendLoading(false);
    }
  };

  useEffect(() => {
    return () => {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
      }
    };
  }, []);

  return (
    <Dialog open={open} onOpenChange={handleDialogChange} modal={true}>
      <DialogContent
        className="sm:max-lg w-full"
        onEscapeKeyDown={(e) => e.preventDefault()}
        onPointerDownOutside={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>{getDialogTitle()}</DialogTitle>
          <DialogDescription>{getDialogDescription()}</DialogDescription>
        </DialogHeader>

        <div className="pt-4">
          {stage === DialogStage.EMAIL && renderEmailStage()}
          {stage === DialogStage.OTP && renderOtpStage()}
          {stage === DialogStage.PASSWORD && renderPasswordStage()}
        </div>
      </DialogContent>
    </Dialog>
  );
}
