import React, { forwardRef } from "react";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, helperText, leftIcon, rightIcon, className = "", id, ...props }, ref) => {
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

    return (
      <div className="flex flex-col gap-1.5 w-full">
        {label && (
          <label htmlFor={inputId} className="text-xs font-semibold text-slate-300 tracking-wide">
            {label}
            {props.required && <span className="text-red-400 ml-1">*</span>}
          </label>
        )}
        <div className="relative flex items-center w-full">
          {leftIcon && (
            <div className="absolute left-3 text-slate-400 pointer-events-none flex items-center justify-center">
              {leftIcon}
            </div>
          )}
          <input
            id={inputId}
            ref={ref}
            className={`w-full bg-slate-900/80 border text-slate-100 text-sm rounded-xl py-2.5 transition-all duration-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 disabled:opacity-50 disabled:cursor-not-allowed ${
              leftIcon ? "pl-10" : "pl-3.5"
            } ${rightIcon ? "pr-10" : "pr-3.5"} ${
              error
                ? "border-red-500/70 focus:border-red-500"
                : "border-slate-700/80 hover:border-slate-600 focus:border-indigo-500"
            } ${className}`}
            {...props}
          />
          {rightIcon && <div className="absolute right-3 text-slate-400 flex items-center justify-center">{rightIcon}</div>}
        </div>
        {error ? (
          <span className="text-xs font-medium text-red-400 mt-0.5">{error}</span>
        ) : helperText ? (
          <span className="text-xs text-slate-400 mt-0.5">{helperText}</span>
        ) : null}
      </div>
    );
  }
);

Input.displayName = "Input";
